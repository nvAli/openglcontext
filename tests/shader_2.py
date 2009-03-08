#! /usr/bin/env python
'''Shader sample-code for OpenGLContext
'''
from OpenGLContext import testingcontext
BaseContext, MainFunction = testingcontext.getInteractive()
from OpenGL.GL import *
from OpenGL.arrays import vbo
from OpenGLContext.arrays import *
from OpenGLContext.scenegraph.shaders import compileProgram, glUseProgram

class TestContext( BaseContext ):
	"""This shader just passes gl_Color from an input array to 
	the fragment shader, which interpolates the values across the 
	face (a "varying" data type).
	"""
	
	def OnInit( self ):
		self.shader = compileProgram(
			'''void main() {
				gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
				gl_FrontColor = gl_Color;
			}''',
			'''void main() {
				gl_FragColor = gl_Color;
			}''',
		)
		self.vbo = vbo.VBO(
			array( [
				[  0, 1, 0,  0,1,0 ],
				[ -1,-1, 0,  1,1,0 ],
				[  1,-1, 0,  0,1,1 ],
				
				[  2,-1, 0,  1,0,0 ],
				[  4,-1, 0,  0,1,0 ],
				[  4, 1, 0,  0,0,1 ],
				[  2,-1, 0,  1,0,0 ],
				[  4, 1, 0,  0,0,1 ],
				[  2, 1, 0,  0,1,1 ],
			],'f')
		)
	
	def Render( self, mode = 0):
		"""Render the geometry for the scene."""
		BaseContext.Render( self, mode )
		glUseProgram(self.shader)
		try:
			self.vbo.bind()
			try:
				glEnableClientState(GL_VERTEX_ARRAY);
				glEnableClientState(GL_COLOR_ARRAY);
				glVertexPointer(3, GL_FLOAT, 24, self.vbo )
				glColorPointer(3, GL_FLOAT, 24, self.vbo+12 )
				glDrawArrays(GL_TRIANGLES, 0, 9)
			finally:
				self.vbo.unbind()
		finally:
			glUseProgram( 0 )
		

if __name__ == "__main__":
	MainFunction ( TestContext)

