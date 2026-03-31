#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 13 March 2019

Super classes for customised use of tui viewer. 

@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""

import sys
import os
import logging
import argparse
from ngawari import fIO
from ngawari import vtkfilters
from tui.tuiUtils import dialogGetName
from tui import tuiViewer
from tui import tuimarkupui
from tui import piwakawakamarkupui
from tui import piwakawakaViewer
import tui as _tui_pkg

logger = logging.getLogger(__name__)



### ====================================================================================================================
### ====================================================================================================================

class _TUIProj(object):

    def __init__(self, app, VERBOSE=False):
        self.app = app
        self.VERBOSE = VERBOSE
        if self.VERBOSE:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    
    def setup(self, inputPath, workDir=None, scalar=None):
        if os.path.isdir(inputPath): # DICOM directory
            srcDir = os.path.split(inputPath)[0]
            self.ex.loadDicomDir(inputPath)
        elif inputPath.lower().endswith('.dcm'): # DICOM file
            srcDir = os.path.split(inputPath)[0]
            self.ex.loadDicomDir(inputPath)
        else: # VTI or PVD file or VTI-DICT
            if isinstance(inputPath, str):
                srcDir = os.path.split(inputPath)[0]
            self.ex.loadVTI_or_PVD(inputPath)

        if workDir is None:
            if srcDir:
                workDir = srcDir
            else:
                workDir = os.getcwd()
        
        self.ex.setWorkingDirectory(workDir)
        logger.info("WORK-DIR set to: %s", workDir)
        if scalar is not None:
            self.ex.setCurrentArray(scalar) # Example to set shown array (else take scalar)


    def getLMPoints_xyz(self, timeID=None):
        if timeID is None:
            timeID = self.ex.currentTimeID
        allMarkupPointsThisTime = self.ex.Markups.getXNumpyFromPoints(timeID)
        return allMarkupPointsThisTime


    def getLMPoints_xyz_time(self):
        outDict = {}
        for k1, iTime in enumerate(self.ex.times):
            outDict[iTime] = self.getLMPoints_xyz(k1)
        return outDict




### ====================================================================================================================
### ====================================================================================================================
class TUIProject(_TUIProj):
    """
    TUIProject super class.
    General saving of markups is handled here.

    See TUIBasic as an example. 
    General idea is to sub-class TUIProject and implement your own functionality and then take advantage of this for outputs. 

    Basic example: 
    You have a algorithm that takes a couple of landmarks and then performs a segmentation. 

    Subclass TUIProject.
    - Update setup() to add your own buttons. 
    - Implement your own actions for these. 

    One function may look something like: 
    
    def my_algorithm(self): 
        landmarks = self.getLMPoints_xyz() # Gets at current timestep
        mask = my_segmentation_from_landmarks(landmarks)

    """
    def __init__(self, app=None, VERBOSE=False):
        if app is None:
            app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
        super().__init__(app)
        self.ex = tuiViewer.TUIMarkupViewer()
        logger.info("TUIProject initialized")
        self.VERBOSE = VERBOSE
        if self.VERBOSE:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def alignBy_X_Norm(self, X, Norm):
        logger.debug("This is centering but not aligning.")
        norm0 = Norm / vtkfilters.np.linalg.norm(Norm)
        norm1, norm2 = [0, 0, 0], [0, 0, 0]
        vtkfilters.vtk.vtkMath.Perpendiculars(norm0, norm1, norm2, 0.3)
        # Set center of view
        self.ex.resliceCursor.SetCenter(X[0], X[1], X[2])  # THIS WORKS
        # Set norms of view
        # self.ex.resliceCursor.SetXViewUp(norm0)  ## THIS IS NOT WHAT WE WANT
        # self.ex.resliceCursor.SetYViewUp(norm1)
        # self.ex.resliceCursor.SetZViewUp(norm2)
        # self.ex.resliceCursor.SetXAxis(norm1)  ## THIS IS WORKING IN LATEST VTK ... 9.2
        # self.ex.resliceCursor.SetYAxis(norm0)
        # self.ex.resliceCursor.SetZAxis(norm2)
        # self.ex.resliceCursorWidgetArray[0].GetResliceCursorRepresentation().GetPlaneSource().SetNormal(norm1) # This moves the slice in the 3D space
        # self.ex.resliceCursorWidgetArray[1].GetResliceCursorRepresentation().GetPlaneSource().SetNormal(norm0)
        # self.ex.resliceCursorWidgetArray[2].GetResliceCursorRepresentation().GetPlaneSource().SetNormal(norm2)
        self.ex.resliceCursor.SetXAxis(norm0[0], norm0[1], norm0[2]) # SHOULD BE THIS: This does nothing
        self.ex.resliceCursor.SetYAxis(norm1[0], norm1[1], norm1[2])
        self.ex.resliceCursor.SetZAxis(norm2[0], norm2[1], norm2[2])
        self.ex.resliceCursor.Update()
        self.ex.renderWindow.Render()
        logger.debug("Norms: %s %s %s viewNormal=%s", norm0, norm1, norm2, self.ex.getViewNormal(0))
        logger.debug("Cursor axes: X=%s Y=%s Z=%s",
                    self.ex.resliceCursor.GetXAxis(),
                    self.ex.resliceCursor.GetYAxis(),
                    self.ex.resliceCursor.GetZAxis())



### ====================================================================================================================
### ====================================================================================================================
class TUI2DProject(_TUIProj):
    """
    TUI2DProject super class.

    """
    def __init__(self, app=None, VERBOSE=False):
        if app is None:
            app = piwakawakamarkupui.QtWidgets.QApplication(['PIWAKAWAKA Image Viewer'])
        super().__init__(app)
        self.ex = piwakawakaViewer.PIWAKAWAKAMarkupViewer()
        logger.info("TUI2DProject initialized")
        self.VERBOSE = VERBOSE
        if self.VERBOSE:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)





### ====================================================================================================================


### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================
class TUIBasic(TUIProject):
    """
    Basic TUI for project based work. 
    Illustrates basic setup and modification of push buttons.
    """
    def __init__(self, app=None):
        TUIProject.__init__(self, app)
        logger.info("TUIBasic initialized")
        self.pushButtonDict = {}


    def setup(self, inputPath, workDir=None, scalar=None):
        super().setup(inputPath, workDir, scalar)

        self.pushButtonDict = {0:['Save points', self.savePolyPts_],
                              1:['Save line', self.savePolyLine_],
                              3:['Clear Markups', self.ex.deleteAllMarkups],
                              4:['Save images', self.saveImages_],
                              5: ['Points to VOI', self.saveVOI_]}

        self.ex.updatePushButtonDict(self.pushButtonDict)


    def saveVOI_(self):
        fOut = self.ex.saveVOI()
        if fOut is not None:
            logger.info("Written VOI to %s", fOut)

    def savePolyPts_(self):
        fOut = self.ex.savePoints()
        if fOut is not None:
            logger.info("Written points to %s", fOut)

    def savePolyLine_(self):
        fOut = self.ex.saveLine(LINE_LOOP=self.ex.splineClosed)
        if fOut is not None:
            logger.info("Written line to %s", fOut)

    def testMask(self):
        logger.info("Does nothing")


    def saveImages_(self):
        pts = self.getLMPoints_xyz()
        VIEW_ID = 2 # TOP LEFT
        self.ex.deleteAllMarkups()
        # FORCE NORMAL
        self.ex.interactionView = VIEW_ID
        nn = vtkfilters.np.array(self.ex.getCurrentViewNormal())
        p1_2 = pts[1] - pts[0]
        p1_2N = p1_2 / vtkfilters.np.linalg.norm(p1_2)
        nn = vtkfilters.ftk.setVecAConsitentWithVecB(nn, p1_2N)
        dd = vtkfilters.ftk.distTwoPoints(pts[0], pts[1])
        endPt = pts[0] + dd * nn
        #
        self.ex.saveImages(self.ex.workingDir, pts[0], endPt, 50, VIEW_ID, outputPrefix='DCM', size=256)
        logger.info("Saved images to %s", self.ex.workingDir)

    # def alignRandom(self):
    #     # NOT WORKING
    #     cp = self.ex.getCurrentVTIObject().GetCenter()
    #     norm = [np.random.rand() for k in range(3)]
    #     self.alignBy_X_Norm(X=cp, Norm=norm)

### ====================================================================================================================
### ====================================================================================================================
class TUI2D(TUI2DProject):
    """
    Basic TUI for project based work. 
    Illustrates basic setup and modification of push buttons.
    """
    def __init__(self, app=None):
        super().__init__(app)
        logger.info("TUI2D initialized")
        self.pushButtonDict = {}


    def setup(self, inputPath, workDir=None, scalar=None):
        super().setup(inputPath, workDir, scalar)

        self.pushButtonDict = {0:['Save points', self.savePolyPts_],
                              1:['Save line', self.savePolyLine_],
                              3:['Clear Markups', self.ex.deleteAllMarkups],
                              5: ['Points to VOI', self.saveVOI_]}

        self.ex.updatePushButtonDict(self.pushButtonDict)


    def saveVOI_(self):
        fOut = self.ex.saveVOI()
        if fOut is not None:
            logger.info("Written VOI to %s", fOut)

    def savePolyPts_(self):
        fOut = self.ex.savePoints()
        if fOut is not None:
            logger.info("Written points to %s", fOut)

    def savePolyLine_(self):
        fOut = self.ex.saveLine(LINE_LOOP=self.ex.splineClosed)
        if fOut is not None:
            logger.info("Written line to %s", fOut)
    



### ====================================================================================================================
### ====================================================================================================================
def launchBasic(inputPath, scalar, workDir):
    app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
    OBJ = TUIBasic(app)
    OBJ.setup(inputPath=inputPath, workDir=workDir, scalar=scalar)
    sys.exit(app.exec_())


def launch2D(inputPath, scalar, workDir):
    app = piwakawakamarkupui.QtWidgets.QApplication(['PIWAKAWAKA Image Viewer'])
    OBJ = TUI2D(app)
    logger.info("Launching 2D viewer")
    OBJ.setup(inputPath=inputPath, workDir=workDir, scalar=scalar)
    sys.exit(app.exec_())


def LaunchCustomApp(TUIApp, subjObj):
    app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
    try:
        OBJ = TUIApp(app)
    except TypeError:
        OBJ = TUIApp(app)
    OBJ.setup(subjObj)
    sys.exit(app.exec_())


### ====================================================================================================================
### ====================================================================================================================
def run(inputFileName, logLevel, scalar=None, workDir=None, TwoD=False):
    """Launch the TUI viewer.

    Args:
        inputFileName: Full filename [.pvd, .vti, .png/jpg, .dcm, directory of DICOM files]
        logLevel: Logging level (e.g. DEBUG, INFO, WARNING, ERROR)
        scalar: Scalar to display
        workDir: Working directory to save markups
        TwoD: Open 2D viewer
    """
    _tui_pkg.configure_logging(level=logLevel)

    if TwoD:
        launch2D(inputFileName, scalar, workDir)
    else:
        launchBasic(inputFileName, scalar, workDir)

def main():
    ap = argparse.ArgumentParser(description='Master', formatter_class=argparse.RawTextHelpFormatter)
    groupR = ap.add_argument_group('Run parameters')
    groupR.add_argument('-in', dest='inputFile', help='full filename [.pvd, .vti, .png/jpg, .dcm]', type=str, default=None)
    groupR.add_argument('-Scalar', dest='Scalar', help='Set scalar', type=str, default=None)
    groupR.add_argument('-workDir', dest='workDir', help='Working directory to save markups', type=str, default=None)
    groupR.add_argument('-2D', dest='TwoD', help='Open 2D viewer', action='store_true')
    groupR.add_argument('-logLevel', dest='logLevel',
                        help='Set log level: DEBUG, INFO, WARNING, ERROR (default: INFO)',
                        type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])

    args = ap.parse_args()
    if args.inputFile is not None:
        log_level = getattr(logging, args.logLevel.upper())
        run(args.inputFile, log_level, args.Scalar, args.workDir, args.TwoD)
    else:
        ap.print_help(sys.stderr)



### ====================================================================================================================
### ====================================================================================================================
if __name__ == '__main__':
    main()





