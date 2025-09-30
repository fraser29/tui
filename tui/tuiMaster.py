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
import argparse
from ngawari import fIO
from ngawari import vtkfilters
from tui.tuiUtils import dialogGetName
from tui import tuiViewer
from tui import tuimarkupui
from tui import piwakawakamarkupui
from tui import piwakawakaViewer



### ====================================================================================================================
### ====================================================================================================================

class _TUIProj(object):

    def __init__(self, app):
        self.app = app

    
    def setup(self, inputPath, workDir=None, scalar=None):
        if os.path.isdir(inputPath): # DICOM directory
            srcDir = os.path.split(inputPath)[0]
            self.ex.loadDicomDir(inputPath)
        elif inputPath.lower().endswith('.dcm'): # DICOM file
            srcDir = os.path.split(inputPath)[0]
            self.ex.loadDicomDir(inputPath)
        else: # VTI or PVD file
            srcDir = os.path.split(inputPath)[0]
            self.ex.loadVTI_or_PVD(inputPath)

        if workDir is None:
            if srcDir:
                workDir = srcDir
            else:
                workDir = os.getcwd()
        
        self.ex.workingDirLineEdit.setText(workDir)
        if self.ex.VERBOSE:
            print("WORK-DIR set to :", workDir)
        if scalar is not None:
            self.ex.setCurrentArray(scalar) # Example to set shown array (else take scalar)


    def getFullFileName(self, fileName=None, prefix=None, extn=None):
        if fileName is None:
            fileName = dialogGetName(self.ex)
        if len(fileName) == 0:
            return
        if prefix is not None:
            if not fileName.startswith(prefix):
                fileName = prefix+fileName
        if extn is not None:
            if not extn.startswith('.'):
                extn = '.'+extn
            if not fileName.endswith(extn):
                fileName = fileName + extn
        return os.path.join(str(self.ex.workingDirLineEdit.text()), fileName)


    def getLMPoints_xyz(self):
        allMarkupPointsThisTime = self.ex.Markups.getXNumpyFromPoints(self.ex.currentTimeID)
        return allMarkupPointsThisTime


    def getLMPoints_xyz_time(self):
        ppDict = self._getMarkupAsPolydata()
        outDict = {}
        for iTime in ppDict.keys():
            outDict[iTime] = vtkfilters.getPtsAsNumpy(ppDict[iTime])
        return outDict


    def _save(self, polyDataDict, featureName=None, prefix='', extn='vtp', FORCE_PVD_EVEN_IF_SINGLE=False):
        if polyDataDict is None:
            return 
        if featureName is None:
            featureName = dialogGetName(self.ex)
        if len(featureName) == 0:
            return
        if len(polyDataDict) == 1 and not FORCE_PVD_EVEN_IF_SINGLE:
            fileOut = self.getFullFileName(fileName=featureName, prefix=prefix, extn=extn)
            fileOut = fIO.writeVTKFile(polyDataDict[self.ex.times[0]], fileOut)
        else:
            fileOut = fIO.writeVTK_PVD_Dict(polyDataDict, 
                                rootDir=self.ex.workingDirLineEdit.text(), 
                                filePrefix=featureName, fileExtn=extn)
        return fileOut


    def saveVOI(self, featureName=None):
        ppDict = self.getVOI_dict()
        return self._save(ppDict, featureName=featureName, prefix='fov')


    def savePoints(self, featureName=None):
        ppDict = self.getPolyDataPoints_dict()
        return self._save(ppDict, featureName=featureName, prefix='pt')


    def saveLine(self, featureName=None, lineLoop=False, splineDist=None, prefix='line'):
        ppDict = self.getPolyDataLine_dict(LOOP=lineLoop, spacing=splineDist)
        return self._save(ppDict, featureName=featureName, prefix=prefix)


    def getPolyDataPoints_dict(self):
        return self._getMarkupAsPolydata()


    def getPolyDataLine_dict(self, LOOP=False, spacing=None):
        ptsDict = self._getMarkupAsPolydata()
        lineDict = {}
        for iTime in ptsDict.keys():
            lineDict[iTime] = vtkfilters.buildPolyLineFromXYZ(vtkfilters.getPtsAsNumpy(ptsDict[iTime]), LOOP=LOOP)
            if spacing is not None:
                lineDict[iTime] = vtkfilters.filterVtpSpline(lineDict[iTime], spacing=spacing)
        return lineDict


    def getVOI_dict(self):
        ptsDict = self._getMarkupAsPolydata()
        voiDict = {}
        for iTime in ptsDict.keys():
            voiDict[iTime] = vtkfilters.getOutline(ptsDict[iTime])
        return voiDict


    def _getMarkupAsPolydata(self):
        outDict = {}
        try:
            for k1 in range(len(self.ex.times)):
                pp = self.ex.Markups.getPolyPointsFromPoints(timeID=k1)
                if pp.GetNumberOfPoints() > 0:
                    outDict[self.ex.times[k1]] = pp
        except (AttributeError, ValueError) as e:
            print(e)
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
        self.ex.VERBOSE = VERBOSE
        

    def alignBy_X_Norm(self, X, Norm):
        print(f"This is centering but not aligning. ")
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
        print(norm0, norm1, norm2, self.ex.getViewNormal(0))
        print(self.ex.resliceCursor.GetXAxis(), self.ex.resliceCursor.GetYAxis(), self.ex.resliceCursor.GetZAxis())



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
        self.ex.VERBOSE = VERBOSE






### ====================================================================================================================


### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================
class TUIBasic(TUIProject):
    """
    Basic TUI for project based work. 
    Illustrates basic setup and modification of push buttons.
    """
    def __init__(self, app=None, VERBOSE=False):
        TUIProject.__init__(self, app, VERBOSE)
        self.pushButtonDict = {}


    def setup(self, inputPath, workDir=None, scalar=None):
        super().setup(inputPath, workDir, scalar)

        self.pushButtonDict = {0:['Save points', self.savePolyPts_],
                              1:['Save line', self.savePolyLine_],
                              3:['Clear Markups', self.ex.deleteAllMarkups],
                              4:['Test mask', self.testMask],
                              5: ['Points to VOI', self.saveVOI_]}

        self.ex.updatePushButtonDict(self.pushButtonDict)


    def saveVOI_(self):
        fOut = self.saveVOI()
        if (fOut is not None) and self.ex.VERBOSE:
            print(f"Written VOI to {fOut}")

    def savePolyPts_(self):
        fOut = self.savePoints()
        if (fOut is not None) and self.ex.VERBOSE:
            print(f"Written points to {fOut}")


    def savePolyLine_(self):
        fOut = self.saveLine(LINE_LOOP=self.ex.splineClosed)
        if (fOut is not None) and self.ex.VERBOSE:
            print(f"Written line to {fOut}")
    

    def testMask(self):
        print("Does nothing")

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
    def __init__(self, app=None, VERBOSE=False):
        super().__init__(app, VERBOSE)
        self.pushButtonDict = {}


    def setup(self, inputPath, workDir=None, scalar=None):
        super().setup(inputPath, workDir, scalar)

        self.pushButtonDict = {0:['Save points', self.savePolyPts_],
                              1:['Save line', self.savePolyLine_],
                              3:['Clear Markups', self.ex.deleteAllMarkups],
                              5: ['Points to VOI', self.saveVOI_]}

        self.ex.updatePushButtonDict(self.pushButtonDict)


    def saveVOI_(self):
        fOut = self.saveVOI()
        if (fOut is not None) and self.ex.VERBOSE:
            print(f"Written VOI to {fOut}")

    def savePolyPts_(self):
        fOut = self.savePoints()
        if (fOut is not None) and self.ex.VERBOSE:
            print(f"Written points to {fOut}")


    def savePolyLine_(self):
        fOut = self.saveLine(LINE_LOOP=self.ex.splineClosed)
        if (fOut is not None) and self.ex.VERBOSE:
            print(f"Written line to {fOut}")
    



### ====================================================================================================================
### ====================================================================================================================
def launchBasic(inputPath, scalar, workDir, VERBOSE=False):
    app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
    OBJ = TUIBasic(app, VERBOSE)
    OBJ.setup(inputPath=inputPath, workDir=workDir, scalar=scalar)
    sys.exit(app.exec_())


def launch2D(inputPath, scalar, workDir, VERBOSE=False):
    app = piwakawakamarkupui.QtWidgets.QApplication(['PIWAKAWAKA Image Viewer'])
    OBJ = TUI2D(app, VERBOSE)
    print("Launching 2D viewer")
    OBJ.setup(inputPath=inputPath, workDir=workDir, scalar=scalar)
    sys.exit(app.exec_())


def LaunchCustomApp(TUIApp, subjObj, VERBOSE=False):
    app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
    try:
        OBJ = TUIApp(app, VERBOSE)
    except TypeError:
        OBJ = TUIApp(app)
    OBJ.setup(subjObj)
    sys.exit(app.exec_())


### ====================================================================================================================
### ====================================================================================================================
def run(inputFileName, scalar=None, workDir=None, TwoD=False, VERBOSE=False):
    if TwoD:
        launch2D(inputFileName, scalar, workDir, VERBOSE)
    else:
        launchBasic(inputFileName, scalar, workDir, VERBOSE)

def main():
    ap = argparse.ArgumentParser(description='Master', formatter_class=argparse.RawTextHelpFormatter)
    groupR = ap.add_argument_group('Run parameters')
    groupR.add_argument('-in', dest='inputFile', help='full filename [.pvd, .vti, .png/jpg, .dcm]', type=str, default=None)
    groupR.add_argument('-Scalar',dest='Scalar',help='Set scalar', type=str, default=None)
    groupR.add_argument('-workDir',dest='workDir',help='Working directory to save markups', type=str, default=None)
    groupR.add_argument('-2D',dest='TwoD',help='Open 2D viewer', action='store_true')
    groupR.add_argument('-VERBOSE',dest='VERBOSE',help='Run in verbose mode',action='store_true')
    # groupR.add_argument('-DEV',dest='DEV',help='Run in development mode',action='store_true')

    args = ap.parse_args()
    if args.inputFile is not None:
        run(args.inputFile, args.Scalar, args.workDir, args.TwoD, args.VERBOSE)
    else:
        ap.print_help(sys.stderr)



### ====================================================================================================================
### ====================================================================================================================
if __name__ == '__main__':
    main()





