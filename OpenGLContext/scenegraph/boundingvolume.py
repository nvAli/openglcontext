"""Bounding volume implementation

Based on code from:
	http://www.markmorley.com/opengl/frustumculling.html

Notes regarding general implementation:

	BoundingVolume objects are generally created by Grouping
	and/or Shape nodes (or rather, the geometry nodes of Shape
	nodes).  Grouping nodes are able to create union
	BoundingVolume objects from their children's bounding
	volumes.

	The RenderPass object (for visiting rendering passes)
	defines a children method which will use the bounding
	volumes to filter out those children which are not visible.

	The first attempt to do that filtering will recursively
	generate and cache the bounding volumes.

	Setting the module-global value DEBUG_RENDER_VOLUMES while
	not running in Python's -O (optimised) mode will draw all
	Axis-aligned bounding boxes (the normal/default volumes)
	as red line-sets.
"""
from OpenGLContext.arrays import *
from OpenGL.GL import *
from OpenGL.GLUT import glutSolidCube
from vrml.vrml97 import nodetypes
from vrml import node, field, protofunctions
from OpenGLContext import frustum, utilities, doinchildmatrix
from OpenGLContext.scenegraph import cache
from OpenGLContext.debug.logs import bounding_log as log
import exceptions

try:
	from vrml.arrays import frustcullaccel
except ImportError:
	frustcullaccel = None

DEBUG_RENDER_VOLUMES = 0

class UnboundedObject( exceptions.ValueError ):
	"""Error raised when an object does not support bounding volumes"""

class BoundingVolume( node.Node ):
	"""Base class for all bounding volumes

	BoundingVolume is both a base class and a functional
	bounding volume which is always considered visible.
	Geometry which wishes to never be visible can return
	a BoundingVolume as their boundingVolume.
	"""
	def visible (self, frustum, matrix=None, occlusion=0, mode=None):
		"""Test whether volume is within given frustum"""
		return 0
	def getPoints( self, ):
		"""Get the points which comprise the volume"""
		return ()
class UnboundedVolume( BoundingVolume ):
	"""A bounding volume which is always visible

	Opposite of a BoundingVolume, geometry can return
	an UnboundedVolume if they always wish to be visible.
	"""
	def visible( self, frustum, matrix=None, occlusion=0, mode=None ):
		"""Test whether volume is within given frustum

		We don't actually do anything here, just return true
		"""
		return 1
	def getPoints( self, ):
		"""Signal to parents that we require unbounded operation"""
		raise UnboundedObject( """Attempt to get union of an unbounded volume""" )

class BoundingBox( BoundingVolume ):
	"""Generic representation of a bounding box

	A bounding box is a bounding volume which is implemented
	as a set of points which can be tested against a frustum.
	Although at the moment we don't use the distinction between
	BoundingBox and AABoundingBox, the BoundingBox may
	eventually be used to provide specialized support for
	bitmap Text nodes (which should only need four points
	to determine their visibility, rather than eight).
	"""
	points = field.newField( 'points', 'MFVec4f', 0, [])
	if frustcullaccel:
		# We have the C extension module, use it
		def visible( self, frust, matrix=None, occlusion=0, mode=None ):
			"""Determine whether this bounding-box is visible in frustum

			frustum -- Frustum object holding the clipping planes
				for the view
			matrix -- a matrix which transforms the local
				coordinates to the (world-space) coordinate
				system in which the frustum is defined.

			This version of the method uses the frustcullaccel
			C extension module to do the actual culling once
			the volume's points are multiplied by the matrix.
			"""
			if matrix is None:
				matrix = frustum.viewingMatrix( )
			points = self.getPoints()
			points = dot( points, matrix )
			if __debug__:
				if DEBUG_RENDER_VOLUMES:
					self.debugRender()
			culled, planeIndex = frustcullaccel.planeCull( frust.planes, points )
			return not culled
	else:
		def visible( self, frust, matrix=None, occlusion=0, mode=None ):
			"""Determine whether this bounding-box is visible in frustum

			frustum -- Frustum object holding the clipping planes
				for the view
			matrix -- a matrix which transforms the local
				coordinates to the (world-space) coordinate
				system in which the frustum is defined.

			This version of the method uses a pure-python loop
			to do the actual culling once the points are
			multiplied by the matrix. (i.e. it does not use the
			frustcullaccel C extension module)
			"""
			if matrix is None:
				matrix = frustum.viewingMatrix( )
			points = self.getPoints()
			points = dot( points, matrix )
			points[:,-1] = 1.0
			if __debug__:
				if DEBUG_RENDER_VOLUMES:
					self.debugRender()
			if frust:
				for plane in frust.planes:
					foundInFront = 0
					for point in points:
						distance = sum(plane*point)
						if distance >= 0:
							# point is in front of plane, so:
							#   this plane can't eliminate the object
							foundInFront = 1
							break
					if not foundInFront:
						#planePoint, planeNormal = utilities.plane2PointNormal(plane)
						# got all the way through, this plane eliminated us!
						return 0
			else:
				log.warn(
					"""BoundingBox visible called with Null frustum""",
				)
			return 1
		
	def getPoints(self):
		"""Return set of points to test against the frustum"""
		return self.points
	def union( boxes, matrix = None ):
		"""Create BoundingBox union for the given bounding boxes

		This uses the getPoints method of the given
		bounding boxes to retrieve the extrema points
		which must be present in the union.  It then
		calculates an Axis-Aligned bounding box shape
		taking into account the matrix given.

		It would seem somewhat more efficient here to
		use the points array directly, but that would
		have the effect of geometrically increasing the
		number of checks for each succeeding parent,
		while creating the axis-aligned bounding box
		trades more work here to keep the constant-time
		operation for the "visible" check.

		Group nodes pass a None as the matrix, while
		Transform nodes should pass their individual
		transformation matrix (not the cumulative matrix).

		boxes -- list of AABoundingBox instances
		matrix -- if specified, the matrix to be applied
			to the box coordinates before calculating the
			resulting axis-aligned bounding box.
		"""
		points = []
		for box in boxes:
			set = box.getPoints()
			if len(set) > 0:
				points.append( set )
		if not points:
			return BoundingVolume()
		points = tuple(points)
		points = concatenate(points)
		if matrix is not None:
			points = dot( points, matrix )
		xes,yes,zes = points[:,0],points[:,1],points[:,2]
		maxX,maxY,maxZ = xes[argmax(xes)],yes[argmax(yes)],zes[argmax(zes)]
		minX,minY,minZ = xes[argmin(xes)],yes[argmin(yes)],zes[argmin(zes)]
		size = maxX-minX, maxY-minY, maxZ-minZ
		result = AABoundingBox(
			center = (
				(size[0])*.5+minX,
				(size[1])*.5+minY,
				(size[2])*.5+minZ,
			),
			size = size,
		)
		return result
	union = staticmethod(union)
	def debugRender( self ):
		"""Render this bounding box for debugging mode

		XXX Should really use points for rendering GL_POINTS
			geometry for the base class when it gets used.
		"""
	
class AABoundingBox( BoundingBox ):
	"""Representation of an axis-aligned bounding box

	The axis-aligned bounding box defines the entire
	bounding box with two pieces of data, a center position
	and a size vector.  Other than this, it is just a
	point-based bounding box implementation.
	"""
	center = field.newField( 'center', 'SFVec3f', 0, (0,0,0))
	size = field.newField( 'size','SFVec3f',0,(0,0,0))
	def visible( self, frust, matrix=None, occlusion=0, mode=None ):
		"""Allow for occlusion-checking as well as frustum culling"""
		result = super( AABoundingBox, self).visible( frust, matrix, occlusion, mode )
		if result and occlusion:
			return self.occlusionVisible( mode=mode )
		return result
	def getPoints(self):
		"""Return set of points to test against the frustum

		If self.points field is not set, will calculate the
		points from the center and size fields.
		"""
		if not len( self.points ):
			cx,cy,cz = self.center
			sx,sy,sz = self.size
			sx /= 2.0
			sy /= 2.0
			sz /= 2.0
			self.points = array([
				(x,y,z,1)
				for x in (cx-sx,cx+sx)
					for y in (cy-sy,cy+sy)
						for z in (cz-sz,cz+sz)
			],'d')
		return self.points
	def debugRender( self ):
		"""Render this bounding box for debugging mode

		Draws the bounding box as a set of lines in the
		current OpenGL matrix (in OpenGLContext's visiting
		pattern, this is the matrix of the parent of the
		node which is determining whether to cull the node
		to which this bounding box is attached)
		"""
		# This code is not OpenGL 3.1 compatible
		points = self.getPoints()
		glDisable(GL_LIGHTING)
		try:
			glColor3f( 1,0,0)
			for set in [
				[points[0],points[1],points[3],points[2]],
				[points[4],points[5],points[7],points[6]],
			]:
				glBegin( GL_LINE_LOOP )
				try:
					for point in set:
						glVertex3dv( point[:3])
				finally:
					glEnd()
			glBegin( GL_LINES )
			try:
				for i in range(4):
					glVertex3dv( points[i][:3])
					glVertex3dv( points[i+4][:3])
			finally:
				glEnd()
		finally:
			glEnable( GL_LIGHTING)
	def occlusionVisible( self, mode=None ):
		"""Render this bounding volume for an occlusion test

		This requires that the GL_HP_occlusion_test
		extension be available.

		Note:
			We will someday want to avoid doing this test
			if the time required to do the occlusion test
			is > the time to render our children.  We don't
			yet have the instrumentation in the rendering
			engine to support that :( .
		"""
		# This code is not OpenGL 3.1 compatible
		from OpenGL.GL.HP import occlusion_test
		glDepthMask(GL_FALSE)
		try:
			if not DEBUG_RENDER_VOLUMES:
				glColorMask(GL_FALSE,GL_FALSE,GL_FALSE,GL_FALSE)
			try:
				glDisable(GL_LIGHTING)
				try:
					glEnable(occlusion_test.GL_OCCLUSION_TEST_HP)
					try:
						doinchildmatrix.doInChildMatrix( self._occlusionRender )
					finally:
						glDisable(occlusion_test.GL_OCCLUSION_TEST_HP)
				finally:
					glEnable(GL_LIGHTING)
			finally:
				glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE)
		finally:
			glDepthMask(GL_TRUE)
		result = glGetBooleanv(occlusion_test.GL_OCCLUSION_TEST_RESULT_HP)
##		if not result:
##			print "occlusion culling eliminated item", self.center, self.size
		return result
	def occlusionRender( self ):
		"""Render this box to screen"""
		doinchildmatrix.doInChildMatrix( self._occlusionRender )
	def _occlusionRender(self):
		"""Do the low-level rendering of the occlusion volume"""
		glTranslate( *self.center )
		glScale( *self.size )
		glutSolidCube( 1.0 )
		
		

def volumeFromCoordinate( node ):
	"""Calculate a bounding volume for a coordinate node

	This should work for all of:
		IndexedFaceSet
		IndexedLineSet
		PointSet
		IndexedPolygons

	This just takes advantage of the common features of the
	coordinate-based geometry types, ignoring the fact
	that individual pieces of geometry may not actually use
	all of the points within a volume.

	Note:
		this method is cache aware, it will return a cached
		bounding box if possible, or calculate and cache the
		bounding box before returning it.

	XXX There is a pathological case which may be encountered
		due to an optimization seen in certain VRML97
		generators. Namely, these generators will create
		an entire file with a single coordinate node with each
		individual piece of geometry indexing into that
		universal coordinate node. This would, in many designs
		provide an optimization because the coordinate node
		would never be swapped out, allowing the geometry to
		remain within the GL as the current vertex/color
		matrices.  In this case, OpenGLContext will have no
		bounding volume optimization at all, as it will take
		rebounding volume of each piece of geometry to be the
		bounding volume of the entire world.
	"""
	current = getCachedVolume( node )
	if current:
		return current
	if (not node) or (not len(node.point)):
		volume = BoundingVolume()
	else:
		xes,yes,zes = node.point[:,0],node.point[:,1],node.point[:,2]
		maxX,maxY,maxZ = xes[argmax(xes)],yes[argmax(yes)],zes[argmax(zes)]
		minX,minY,minZ = xes[argmin(xes)],yes[argmin(yes)],zes[argmin(zes)]
		size = maxX-minX, maxY-minY, maxZ-minZ
		volume = AABoundingBox(
			center = (
				(size[0])/2+minX,
				(size[1])/2+minY,
				(size[2])/2+minZ,
			),
			size = size,
		)
	if node:
		# note that even if not node.point, we
		# are dependent on that NULL node.point value
		dependencies = [ (node,'point') ]
	else:
		dependencies = []
	return cacheVolume( node, volume, dependencies )

### Abstraction/indirection for caching bounding volumes
##  Because the code to cache bounding volumes is generally
##  identical, we provide this set of two utility methods
##  to retrieve and cache the volumes with proper dependency
##  setup.
def cacheVolume( node, volume, nodeFieldPairs=()):
	"""Cache bounding volume for the given node

	node -- the node associated with the volume
	volume -- the BoundingVolume object to be cached
	nodeFieldPairs -- set of (node,fieldName) tuples giving
		the dependencies for the volume.  Should normally
		include the node itself. If fieldName is None
		a dependency is created on the node itself.
	"""
	holder = cache.CACHE.holder(node, key = "boundingVolume", data = volume )
	for (n, attr) in nodeFieldPairs:
		if n:
			if attr is not None:
				holder.depend( n, protofunctions.getField( n,attr) )
			else:
				holder.depend( n, None )
	return volume
def getCachedVolume( node ):
	"""Get currently-cached bounding volume for the node or None"""
	return cache.CACHE.getData(node, key="boundingVolume")


class BoundingSphere( BoundingVolume):
	"""Representation of a geometry bounding-sphere (unfinished)

	XXX Note: this implementation is not used, and will
		either need to be removed or finished. That shouldn't
		be a particularly difficult project, as the
		frustcullaccel module was written to support bounding
		sphere calculations, it's just that the benefits
		don't really promise to be worth the effort.
	"""
	center = field.newField( 'center', 'SFVec3f', 0, (0,0,0))
	radius = field.newField( 'radius','SFFloat',0,0.0)
	def visible( self, frust, matrix=None, occlusion=0, mode=None ):
		"""Determine whether this bounding-sphere is visible in frustum"""
		if matrix is None:
			matrix = frustum.viewingMatrix( )
		(x,y,z) = self.center
		(x,y,z,w) = dot(matrix, (x,y,z,0))
		radius = self.radius
		for (px,py,pz,pw) in frust.planes:
			foundInFront = 0
			distance = (px*x + py*y + pz*z + pw)
			if distance >= -radius:
				# this plane can't eliminate the object
				foundInFront = 1
				break
			if not foundInFront:
				# got all the way through, this plane eliminated us!
				return 0
		return 1
	def union( boxes, matrix = None ):
		"""Create BoundingBox union for the given bounding boxes
		"""
		raise NotImplemented ("""BoundingSphere objects do not yet have a union method""")
	union = staticmethod (union)
