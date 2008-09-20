#! /usr/bin/env python
'''Test FreeGLUT glutMouseWheelFunc extension to GLUT
'''
from OpenGLContext import testingcontext
BaseContext, MainFunction = testingcontext.getInteractive( ('glut',) )
from OpenGL.GL import *
from OpenGL.GLUT import *

class TestContext( BaseContext ):
	initialPosition = (0,0,5) # set initial camera position, tutorial does the re-positioning
	def Render( self, mode ):
		"""Do basic rendering"""
		result = BaseContext.Render( self, mode )
		glClearColor( 0,0,0, 0)
		glClear(GL_COLOR_BUFFER_BIT)
		glRasterPos( 0,0,0)
		glutBitmapString( GLUT_BITMAP_8_BY_13, "The quick brown\nfox jumped over the\nlazy dog." )
		return result
	def OnInit( self ):
		"""Load the image on initial load of the application"""
		print 'Tests FreeGLUT extensions to the GLUT API'
		glutMouseWheelFunc( self.OnMouseWheel )
		glutWMCloseFunc( self.OnGLUTCloseWM )
		glutCloseFunc( self.OnGLUTClose )
		glutSetOption( GLUT_WINDOW_CURSOR, GLUT_CURSOR_SPRAY )
		glutSetOption( GLUT_ACTION_ON_WINDOW_CLOSE, GLUT_ACTION_GLUTMAINLOOP_RETURNS )
	def OnMouseWheel( self, button,state,x,y):
		"""Just capture and report scrolling"""
		print 'Mouse Wheel button=%s state=%s (x,y)=(%s,%s)'%(button, state, x,y)
	def OnGLUTClose( self, ):
		"""Just capture and report"""
		print 'Close'
	def OnGLUTCloseWM( self, ):
		"""Just capture and report"""
		print 'CloseWM'

if __name__ == "__main__":
	MainFunction ( TestContext)
	print 'Code after the mainloop exits'
	

