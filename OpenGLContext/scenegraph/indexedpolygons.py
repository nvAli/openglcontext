"""Indexed data array geometry type"""
from vrml.vrml97 import nodetypes
from vrml import node, field, protofunctions
from OpenGLContext.scenegraph import coordinatebounded
from OpenGLContext import triangleutilities
from OpenGLContext.scenegraph import polygonsort
from OpenGL.arrays import vbo

from OpenGL.GL import *
from OpenGLContext.arrays import *
from OpenGLContext.debug.logs import geometry_log
from math import pi

class VBOHolder( object ):
	"""Substitutes as object to hold vbo values"""

class IndexedPolygons (
	coordinatebounded.CoordinateBounded,
	nodetypes.Geometry,
	node.Node
):
	"""Simplified indexed polygon geometry type

	IndexedPolygons provide a simpler mechanism than
	the IndexedFaceSet objects for rendering common
	geometric data sets such as those generated by
	common 3-D modelers.

	IndexedPolygons are basically a set of vertices
	which are compiled so that the individual vertices
	are available as equally-indexed arrays of data
	values, i.e. vertex No. 24 would be represented by:

		coord.point[23]
		color.color[23] # optional
		normal.vector[23] # optional
		texCoord.point[23] # optional

	Note that there is no normal generation available
	also note that only 3 or 4-vertex polygons are
	allowed.

	Basically, the IndexedPolygons node consists of
	a set of data arrays which are enabled or disabled
	by their presence in the node.  Rendering is
	accomplished using the glDrawElementsui function,
	which draws the indexed arrays using the indices
	given.  This allows for very efficient updating
	of the data arrays, since the data arrays are not
	pre-processed by the node at all before rendering.
	"""
	#Fields
	polygonSides = field.newField( 'polygonSides', 'SFInt32', 0, 3)
	index = field.newField( 'index', 'MFUInt32', 0, list)
	normal = field.newField( 'normal', 'SFNode', 1, node.NULL)
	solid = field.newField( 'solid', 'SFBool', 0, 1)
	ccw = field.newField( 'ccw', 'SFBool', 0, 1)
	texCoord = field.newField( 'texCoord', 'SFNode', 1, node.NULL)
	color = field.newField( 'color', 'SFNode', 1, node.NULL)
	coord = field.newField( 'coord', 'SFNode', 1, node.NULL)
	def render(
		self,
		visible = 1, # can skip normals and textures if not
		lit = 1, # can skip normals if not
		textured = 1, # can skip textureCoordinates if not
		transparent = 0, # need to sort triangle geometry...
		mode = None, # the renderpass object for which we compile
	):
		"""Render the IndexedPolygons

		visible -- can skip normals and textures if not
		lit - can skip normals if not
		textured -- can skip textureCoordinates if not
		transparent -- need to sort triangle geometry...
		"""
		#print 'indexed polygons', len(self.index), bool(self.coord), bool(self.normal), bool(self.texCoord), bool(self.color)
		#print self.toString()
		if not len(self.index):
			return 1
		glPushClientAttrib(GL_CLIENT_ALL_ATTRIB_BITS)
		glPushAttrib(GL_ALL_ATTRIB_BITS)
		try:
			vbos = self.get_vbos(mode)
			if not self._enableCoords(vbos=vbos):
				return 1
			if visible:
				# potentially enable colour and texture arrays
				# do we have a colour-array to enable
				self._enableColors(vbos=vbos)
			if textured:
				self._enableTextures(vbos=vbos)
			if lit:
				self._enableNormals(vbos=vbos)
				
			# calculate GL constant for # of sides
			if self.polygonSides == 3:
				constant = GL_TRIANGLES
			elif self.polygonSides == 4:
				constant = GL_QUADS
			else:
				raise ValueError ("""%s node has unsupported polygonSides value %s (3 or 4 expected)"""% (str(self), self.polygonSides))
			if self.ccw:
				glFrontFace( GL_CCW )
			else:
				glFrontFace( GL_CW )
			
			if self.solid:# and not transparent:
				glEnable( GL_CULL_FACE )
			else:
				glDisable( GL_CULL_FACE )

			# do the actual rendering
			if visible and transparent:
				self.drawTransparent(constant, mode=mode)
			else:
				glDrawElementsui(
					constant,
					self.index,
				)
		finally:
			glPopAttrib()
			glPopClientAttrib()
		return 1
	def _enableColors( self, vbos):
		"""Enable the colour array if possible"""
		color = vbos.color
		if len(color):
			# make the color field alter the diffuse color
			glColorMaterial( GL_FRONT_AND_BACK, GL_DIFFUSE)
			glEnable( GL_COLOR_MATERIAL )
			self.callBound( glColorPointerd, color )
			glEnableClientState( GL_COLOR_ARRAY )
			return 1
		else:
			return 0
	def _enableNormals( self, vbos ):
		"""Enable the normal array if possible"""
		normal = vbos.normal
		if len(normal):
			# make the color field alter the diffuse color
			self.callBound( glNormalPointerd , normal )
			glEnableClientState( GL_NORMAL_ARRAY )
			glEnable(GL_NORMALIZE); # should do this explicitly eventually
			return 1
		else:
			glDisable( GL_LIGHTING )
			geometry_log.warn(
				"""%s does not define normals, but is being rendered as lit geometry! This is likely an error in your content""",
				self,
			)
			return 0
	def _enableTextures( self, vbos ):
		"""Enable the normal array if possible"""
		tex = vbos.texCoord
		if len(tex):
			self.callBound( glTexCoordPointerd, tex )
			glEnableClientState( GL_TEXTURE_COORD_ARRAY )
			return 1
		else:
			return 0
	def _enableCoords( self, vbos):
		"""Enable the point array if possible"""
		coord = vbos.coord
		if len(coord):
			self.callBound( glVertexPointerd, coord )
			glEnableClientState(GL_VERTEX_ARRAY);
			return 1
		else:
			return 0
	
	def drawTransparent( self, constant, mode=None ):
		"""Fairly complex mechanism for drawing sorted polygons"""
		# we have to create a temporary array of centres for
		# each polygon, that requires taking the centres and then
		# creating an index-set that re-orders the polygons...
		centers = mode.cache.getData(self, key='centers')
		if centers is None:
			## cache centers for future rendering passes...
			ordered_points = take( 
				self.coord.point, self.index.astype('i'), 0 
			)
			centers = triangleutilities.centers(
				ordered_points,
				vertexCount=self.polygonSides,
				components = 3,
			)
			holder = mode.cache.holder(self, key = "centers", data = centers)
			for name in ("polygonSides", "index", "coord"):
				field = protofunctions.getField( self, name )
				holder.depend( self, field )
			for (n, attr) in [
				(self.coord, 'point'),
			]:
				if n:
					holder.depend( n, protofunctions.getField( n,attr) )
		assert centers is not None
		
		# get distances to the viewer
		centers = polygonsort.distances(
			centers
		)
		assert len(centers) == len(self.index)//self.polygonSides
		# get the center indices in sorted order
		indices = argsort( centers )
		sortedIndices = self.index[:]
		sortedIndices = reshape( sortedIndices, (-1,self.polygonSides))
		sortedIndices = take( sortedIndices, indices, 0 )
		

		# okay, now we can render...
		glDrawElementsui(
			constant,
			sortedIndices,
		)
		
	NODE_FIELDS = [
		('coord','point'),
		('normal','vector'),
		('color','color'),
		('texCoord','point'),
	]
	def get_vbos( self, mode):
		"""Retrieve vertex buffer object source if we support them or None if not"""
		if vbo.get_implementation():
			vbos = mode.cache.getData(self, key='vbos')
			if vbos is None:
				vbos = VBOHolder()
				# compile our data to a set of vbos 
				holder = mode.cache.holder(self, key = "vbos", data = vbos)
				for field,attr in self.NODE_FIELDS:
					node = getattr( self, field )
					value = getattr( node, attr, ())
					if len(value):
						setattr( vbos,field, vbo.VBO( value ))
						holder.depend( node, attr )
					else:
						setattr( vbos,field, value)
					holder.depend( self, field )
		else:
			vbos = VBOHolder()
			for field,attr in self.NODE_FIELDS:
				node = getattr( self, field )
				if node:
					value = getattr( node, attr, ())
					if len(value):
						setattr( vbos,field, vbo.VBO( value ))
		return vbos
	def callBound( self, function, array ):
		if hasattr( array, 'bind' ):
			array.bind()
			try:
				return function(array)
			finally:
				array.unbind()
		else:
			return function(array)
