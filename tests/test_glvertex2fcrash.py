#! /usr/bin/env python
'''Test of the glVertex function (draws flower)'''
from __future__ import print_function
from OpenGLContext import testingcontext
BaseContext = testingcontext.getInteractive()
from OpenGL.GL import *

class TestContext( BaseContext ):
    def OnInit( self ):
        """Initialisation"""
        print("""Should raise TypeError (and catch it to display message)""")
    def Render( self, mode = 0):
        BaseContext.Render( self, mode )
        glBegin( GL_TRIANGLES )
        try:
            glVertex2fv( None )
        except (TypeError,ValueError):
            print('Got expected TypeError on attempting to pass None to glVertex2fv')
        glEnd()

if __name__ == "__main__":
    TestContext.ContextMainLoop()
