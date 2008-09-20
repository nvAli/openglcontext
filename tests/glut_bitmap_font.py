#! /usr/bin/env python
'''Low-level GLUT bitmap fonts test'''
from OpenGLContext.tests import _bitmap_font, _fontstyles
from OpenGLContext.scenegraph.text import glutfont

class TestContext( _bitmap_font.TestContext ):
	testingClass = glutfont.GLUTBitmapFont
if __name__ == "__main__":
	_bitmap_font.MainFunction ( TestContext)
