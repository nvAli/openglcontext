"""Flat rendering mechanism using structural scenegraph observation"""
from OpenGLContext.scenegraph import nodepath
from OpenGL.GL import *
from OpenGL.GLU import gluUnProject
from OpenGLContext.arrays import array, dot
from vrml.vrml97 import nodetypes
from vrml import olist
from vrml.vrml97.transformmatrix import RADTODEG
import weakref,random, sys, ctypes
from pydispatch.dispatcher import connect

if sys.maxint > 2L<<32:
	BIGINTS = True 
else:
	BIGINTS = False

class FlatPass( object ):
	"""Flat rendering pass with a single function to render scenegraph 
	
	Uses structural scenegraph observations to allow the actual
	rendering pass be a simple iteration over the paths known 
	to be active in the scenegraph.
	"""
	passCount = 0
	visible = True 
	transparent = False 
	transform = True
	lighting = True
	lightingAmbient = True
	lightingDiffuse = True
	
	selectNames = False
	selectForced = False

	cache = None
	
	INTERESTING_TYPES = [
		nodetypes.Rendering,
		nodetypes.Bindable,
		nodetypes.Light,
		nodetypes.Traversable,
		nodetypes.Background,
		nodetypes.TimeDependent,
		nodetypes.Fog,
		nodetypes.Viewpoint,
		nodetypes.NavigationInfo,
	]
	def __init__( self, scene, contexts ):
		self.scene = scene 
		self.contexts = contexts
		self.paths = {
		}
		self.nodePaths = {}
		self.integrate( scene )
		connect(
			self.onChildAdd,
			signal = olist.OList.NEW_CHILD_EVT,
		)
		connect(
			self.onChildRemove,
			signal = olist.OList.DEL_CHILD_EVT,
		)
	def integrate( self, node, parentPath=None ):
		"""Integrate any children of node which are of interest"""
		if parentPath is None:
			parentPath = nodepath.NodePath( [] )
		todo = [ (node,parentPath) ]
		while todo:
			next,parents = todo.pop(0)
			path = parents + next 
			np = self.npFor( next )
			np.append( path )
			if hasattr( next, 'bind' ):
				for context in self.contexts:
					context = context()
					if context is not None:
						next.bind( context )
			after = self.npFor(next)
			for typ in self.INTERESTING_TYPES:
				if isinstance( next, typ ):
					self.paths.setdefault( typ, []).append( path )
			if hasattr(next, 'renderedChildren'):
				# watch for next's changes...
				for child in next.renderedChildren( ):
					todo.append( (child,path) )
	def npFor( self, node ):
		"""For some reason setdefault isn't working for the weakkeydict"""
		current = self.nodePaths.get( id(node) )
		if current is None:
			self.nodePaths[id(node)] = current = []
		return current
	def onChildAdd( self, sender, value ):
		"""Sender has a new child named value"""
		if hasattr( sender, 'renderedChildren' ):
			children = sender.renderedChildren()
			if value in children:
				for path in self.npFor( sender ):
					self.integrate( value, path )
	def onChildRemove( self, sender, value ):
		"""Invalidate all paths where sender has value as its child IFF child no longer in renderedChildren"""
		if hasattr( sender, 'renderedChildren' ):
			children = sender.renderedChildren()
			if value not in children:
				for path in self.npFor( sender ):
					for childPath in path.iterchildren():
						if childPath[-1] is value:
							childPath.invalidate()
				self.purge()
	def purge( self ):
		"""Purge all references to path"""
		for key,values in self.paths.items():
			filtered = []
			for v in values:
				if not v.broken:
					filtered.append( v )
				else:
					np = self.npFor( v )
					while v in np:
						np.remove( v )
					if not np:
						try:
							del self.nodePaths[id(v)]
						except KeyError, err:
							pass
			self.paths[key][:] = filtered
	def currentBackground( self ):
		"""Find our current background node"""
		paths = self.paths.get( nodetypes.Background, () )
		for background in paths:
			if background[-1].bound:
				return background
		if paths:
			current = paths[0]
			current[-1].bound = 1
			return current 
		return None
	
	def Render( self, context, mode ):
		"""Render the geometry attached to this performer's scenegraph"""
		vp = context.getViewPlatform()
		# clear the projection matrix set up by legacy sg
		glMatrixMode( GL_PROJECTION )
		glLoadMatrixd( self.getProjection() )
		glMatrixMode( GL_MODELVIEW )
		matrix = self.getModelView()
		glLoadIdentity()


		# ordered set of things to work with...
		matrices = [
			(dot(p.transformMatrix(),matrix),p)
			for p in self.paths[ nodetypes.Rendering ]
		]
		toRender = [
			(p[-1].sortKey( mode,m ), m, p )
			for (m,p) in matrices
		]
		toRender.sort( key = lambda x: x[0])


		events = context.getPickEvents()
		if events:
			self.selectRender( mode, toRender, events )
			events.clear()
#			glClear( GL_DEPTH_BUFFER_BIT|GL_COLOR_BUFFER_BIT )
		glLoadIdentity()
		self.matrix = matrix
		self.visible = True
		self.transparent = False 
		self.lighting = True
		self.textured = True 
		

		bPath = self.currentBackground( )
		if bPath is not None:
			glMultMatrixf( vp.quaternion.matrix( dtype='f') )
			bPath.transform(mode, translate=0,scale=0, rotate=1 )
			bPath[-1].Render( mode=mode, clear=(mode.passCount==0) )
		elif mode.passCount == 0:
			### default VRML background is black
			glClearColor(0.0,0.0,0.0,1.0)
			glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT )
		# Set up generic "geometric" rendering parameters
		glDisable( GL_CULL_FACE )
		glFrontFace( GL_CCW )
		glEnable(GL_DEPTH_TEST)
		glEnable(GL_LIGHTING)
		glDepthFunc(GL_LESS)
		glEnable(GL_CULL_FACE)
		glCullFace(GL_BACK)
		
		# okay, now visible presentations
		id = 0
		for path in self.paths.get( nodetypes.Light, ()):
			tmatrix = path.transformMatrix()
			
			localMatrix = dot(tmatrix,matrix)
			self.matrix = localMatrix
			glLoadMatrixd( localMatrix )
			
			path[-1].Light( GL_LIGHT0+id, mode=mode )
			id += 1
			if id >= (self.MAX_LIGHTS-1):
				break
		if not id:
			# default VRML lighting...
			from OpenGLContext.scenegraph import light
			l = light.DirectionalLight( direction = (0,0,-1.0))
			glLoadMatrixd( matrix )
			l.Light( GL_LIGHT0, mode = mode )
		transparentSetup = False
		# TODO: query render for all objects...
		
		for key,tmatrix,path in toRender:
			self.matrix = tmatrix
			glLoadMatrixd( tmatrix )
			self.transparent = key[0]
			if key[0] != transparentSetup:
				glEnable(GL_BLEND);
				glEnable(GL_DEPTH_TEST);
				glBlendFunc(GL_ONE_MINUS_SRC_ALPHA,GL_SRC_ALPHA, )
				glDepthMask( 0 )
			if key[0]:
				path[-1].RenderTransparent( mode=self )
			else:
				path[-1].Render( mode=self )
		glDisable(GL_BLEND);
		glEnable(GL_DEPTH_TEST);
		glDepthMask( 1 ) # allow updates to the depth buffer
		self.matrix = matrix
		
	def selectRender( self, mode, toRender, events ):
		"""Render each of these paths to color buffer"""
		glClear( GL_DEPTH_BUFFER_BIT|GL_COLOR_BUFFER_BIT )
		glDisable( GL_LIGHTING )
		glEnable( GL_COLOR_MATERIAL )
		self.visible = False
		self.transparent = False 
		self.lighting = False
		self.textured = False 
		matrix = self.matrix
		map = {}
		idHolder = array( [0,0,0,0], 'b' )
		idSetter = idHolder.view( '<I' )
		for id,(key,tmatrix,path) in enumerate(toRender):
			id += 50
			idSetter[0] = id
			glColor4bv( idHolder )
			self.matrix = tmatrix
			glLoadMatrixd( tmatrix )
			path[-1].Render( mode=self )
			map[id] = path 
		pickPoints = {}
		for event in events.values():
			key = tuple(event.getPickPoint())
			pickPoints.setdefault( key, []).append( event )
		for point,eventSet in pickPoints.items():
			# get the pixel colour (id) under the cursor.
			pixel = glReadPixels( point[0],point[1],1,1,GL_RGBA,GL_BYTE )
			pixel = long( pixel.view( '<I' )[0][0][0] )
			paths = map.get( pixel, [] )
			event.setObjectPaths( [paths] )
			# get the depth value under the cursor...
			pixel = glReadPixels( point[0],point[1],1,1,GL_DEPTH_COMPONENT,GL_FLOAT )
			event.viewCoordinate = point[0],point[1],pixel[0][0]
			event.modelViewMatrix = matrix
			event.projectionMatrix = self.projection
			event.viewport = self.viewport
			if hasattr( mode.context, 'ProcessEvent'):
				mode.context.ProcessEvent( event )
		glColor4f( 0.0,0.0,0.0, 1.0)
		glDisable( GL_COLOR_MATERIAL )
	
	def textureSort( self, paths ):
		"""Sort paths by texture usage as texture-set, path-set sets"""
	def appearanceGroup( self, paths ):
		"""Group paths according to appearance values"""
		
	MAX_LIGHTS = -1
	def __call__( self, context ):
		"""Overall rendering pass interface for the context client"""
		mode = self 
		vp = context.getViewPlatform()
		# These values are temporarily stored locally, we are 
		# in the context lock, so we're not causing conflicts
		if self.MAX_LIGHTS == -1:
			self.MAX_LIGHTS = glGetIntegerv( GL_MAX_LIGHTS )
		self.context = context
		self.cache = context.cache
		self.projection = vp.viewMatrix()
		self.viewport = (0,0) + context.getViewPort()
		self.modelView = vp.modelMatrix()
		self.eyePoint = vp.position
		
		# We're here setting up legacy OpenGL settings 
		# eventually these will be uniform setups...
		self.Render( context, self )
		return True # flip yes, for now we always flip...

	def getProjection (self):
		"""Retrieve the projection matrix for the rendering pass"""
		return self.projection
	def getViewport (self):
		"""Retrieve the viewport parameters for the rendering pass"""
		return self.viewport
	def getModelView( self ):
		"""Retrieve the base model-view matrix for the rendering pass"""
		return self.modelView

