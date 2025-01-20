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
from TTK import tuiViewer
from TTK import tuimarkupui
from TTK.tuiUtils import dialogGetName



### ====================================================================================================================

class TUIProject(object):
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
        landmarks = self.getLMPoints_xyz(minN=2)
        mask = my_segmentation_from_landmarks(landmarks)
        self.saveMask(mask) # This will open dialogue to save file. 

    """
    def __init__(self, app=None):
        if app is None:
            app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
        self.app = app
        self.ex = tuiViewer.TUIMarkupViewer()
        self.DEBUG = False


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


    def getLMPoints_xyz(self, minN=1):
        allMarkupPointsThisTime = self.ex.Markups.getXNumpyFromPoints(self.ex.currentTimeID)
        if len(allMarkupPointsThisTime) < minN:
            raise ValueError('Not enough points for requested: Need %d, have %d'%(minN, len(allMarkupPointsThisTime)))
        return allMarkupPointsThisTime


    def getLMPoints_poly(self, minN=1, RETURN_LINE=False, LINE_LOOP=True):
        if RETURN_LINE:
            pointsPP = self.ex.Markups.getPolylineFromPoints(self.ex.currentTimeID, LOOP=LINE_LOOP)
        else:
            pointsPP = self.ex.Markups.getPolyPointsFromPoints(self.ex.currentTimeID)
        if pointsPP.GetNumberOfPoints() < minN:
            raise ValueError('Not enough points for requested: Need %d, have %d'%(minN, pointsPP.GetNumberOfPoints()))
        return pointsPP

    def _save(self, polyData, featureName=None, prefix='', extn='vtp'):
        if featureName is None:
            featureName = dialogGetName(self.ex)
        if len(featureName) == 0:
            return
        fileOut = self.getFullFileName(fileName=featureName, prefix=prefix, extn=extn)
        fIO.writeVTKFile(polyData, fileOut)
        return fileOut


    def saveVOI(self, featureName=None):
        print(featureName)
        pp = self._getMarkupAsPolydata(minN=4, BUILD_OUTLINE=True)
        return self._save(pp, featureName=featureName, prefix='fov')


    def savePoints(self, featureName=None, minN=1):
        pp = self._getMarkupAsPolydata(minN=minN, BUILD_LMPts=True)
        return self._save(pp, featureName=featureName, prefix='pt')


    def saveLine(self, featureName=None, minN=2, lineLoop=False, splineDist=None, prefix='line'):
        pp = self._getMarkupAsPolydata(minN=minN, BUILD_LINE=True, LINE_LOOP=lineLoop)
        if splineDist is not None:
            pp = vtkfilters.filterSpline(pp, splineDist)
        return self._save(pp, featureName=featureName, prefix=prefix)


    def saveMask(self, featureName=None): # TODO - this currently just simple shrinkwrap
        pp = self._getMarkupAsPolydata(minN=4, BUILD_MASK=True)
        return self._save(pp, featureName=featureName, prefix='mask')


    def _getMarkupAsPolydata(self, minN=1, BUILD_LMPts=False,
               BUILD_SPHERE=False, BUILD_OUTLINE=False, BUILD_MASK=False, BUILD_LINE=False, LINE_LOOP=True):
        try:
            pointsPP = self.getLMPoints_poly(minN, RETURN_LINE=BUILD_LINE, LINE_LOOP=LINE_LOOP)
        except ValueError as e:
            print(e)
            return
        if BUILD_SPHERE:
            R = vtkfilters.getPolyMeanRadius(pointsPP, EXCLUDE_CENTER=False)
            X = pointsPP.GetCenter()
            ss = vtkfilters.buildSphereSource(X, R)
            ss = vtkfilters.filterTriangulate(ss)
            return ss
        if BUILD_LMPts:
            return pointsPP
        if BUILD_LINE:
            return pointsPP
        if BUILD_MASK:
            mask = vtkfilters.shrinkWrapData(pointsPP)
            return mask
        if BUILD_OUTLINE:
            oo = vtkfilters.getOutline(pointsPP)
            return oo
        return pointsPP


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
### ====================================================================================================================
### ====================================================================================================================
class TUIBasic(TUIProject):
    """
    Basic TUI for project based work. 
    Illustrates basic setup and modification of push buttons.
    """
    def __init__(self, app=None):
        TUIProject.__init__(self, app)
        self.pushButtonDict = {}


    def setup(self, imageFile=None, dicomDir=None, workDir=None):
        if imageFile is not None:
            srcDir = os.path.split(imageFile)[0]
            self.ex.loadVTI_or_PVD(imageFile)
        elif dicomDir is not None:
            srcDir = os.path.split(dicomDir)[0]
            self.ex.loadDicomDir(dicomDir)
        if workDir is None:
            if srcDir:
                workDir = srcDir
            else:
                workDir = os.getcwd()
        self.ex.workingDirLineEdit.setText(workDir)
        # self.ex.setCurrentArray('PixelData') # Example to set shown array (else take scalar)

        self.pushButtonDict = {0:['Save points', self.savePolyPts_],
                              1:['Save line', self.savePolyLine_],
                              3:['Clear Markups', self.ex.deleteAllMarkups],
                            #   4:['Align Random', self.alignRandom],
                              5: ['Points to VOI', self.saveVOI_]}

        self.ex.updatePushButtonDict(self.pushButtonDict)

    def saveVOI_(self):
        fOut = self.saveVOI()
        print(fOut)

    def savePolyPts_(self):
        fOut = self.savePoints()
        print(fOut)


    def savePolyLine_(self):
        fOut = self.saveLine(minN=2)
        print(fOut)
    
    # def alignRandom(self):
    #     # NOT WORKING
    #     cp = self.ex.getCurrentVTIObject().GetCenter()
    #     norm = [np.random.rand() for k in range(3)]
    #     self.alignBy_X_Norm(X=cp, Norm=norm)


### ====================================================================================================================
### ====================================================================================================================
def launchBasic(inputPath):
    app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
    OBJ = TUIBasic(app)

    if os.path.isdir(inputPath):
        OBJ.setup(dicomDir=inputPath)
    elif inputPath.lower().endswith('.dcm'):
        OBJ(dicomDir=os.path.split(inputPath)[0])
    else:
        OBJ.setup(imageFile=inputPath)
    sys.exit(app.exec_())


def LaunchCustomApp(TUIApp, subjObj):
    app = tuimarkupui.QtWidgets.QApplication(['TUI Image Viewer'])
    OBJ = TUIApp(app)
    OBJ.setup(subjObj)
    sys.exit(app.exec_())


### ====================================================================================================================
### ====================================================================================================================
def main(inputFileName, scalar=''):
    launchBasic(inputFileName)


### ====================================================================================================================
### ====================================================================================================================
if __name__ == '__main__':

    ap = argparse.ArgumentParser(description='Master', formatter_class=argparse.RawTextHelpFormatter)
    groupR = ap.add_argument_group('Run parameters')
    groupR.add_argument('-in', dest='inputFile', help='full filename [.pvd, .vti, .png/jpg, .dcm]', type=str, default=None)
    groupR.add_argument('-Scalar',dest='Scalar',help='Set scalar', type=str, default='')
    # groupR.add_argument('-DEV',dest='DEV',help='Run in development mode',action='store_true')

    args = ap.parse_args()
    if args.inputFile is not None:
        main(args.inputFile, args.Scalar)
    else:
        ap.print_help(sys.stderr)







