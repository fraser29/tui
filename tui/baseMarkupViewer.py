#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 13 March 2019

Base viewer class for common functionality between 2D and 3D viewers.

@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""

import os
import vtk
import numpy as np
from ngawari import fIO
from ngawari import vtkfilters
import spydcmtk
from tui import tuiMarkups
from tui.tuiUtils import dialogGetName

from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor # type: ignore

INDEX_OFFSET = 1

outputWindow = vtk.vtkOutputWindow()
outputWindow.SetGlobalWarningDisplay(0)
vtk.vtkObject.SetGlobalWarningDisplay(0)
vtk.vtkLogger.SetStderrVerbosity(vtk.vtkLogger.VERBOSITY_ERROR)


class BaseMarkupViewer:
    """
    Base class for markup viewers with common functionality.
    Provides animation, window level, and basic markup functionality.
    """
    
    def __init__(self, VERBOSE=False):
        # Common defaults
        self.vtiDict = None
        self.patientMeta = spydcmtk.dcmVTKTK.PatientMeta()
        self.currentTimeID = 0
        self.currentArray = ''
        self.times = []
        self.scalarRange = {'Default':[0,255]}
        self.boundingDist = 0.0
        self.multiPointFactor = 0.0001
        self.workingDir = os.getcwd()
        
        # Markup mode settings
        self.markupMode = 'Point'  # 'Point' or 'Spline'
        self.splineClosed = True  # Whether splines should be closed
        
        # Animation settings
        self.isAnimating = False
        self.animationTimer = None
        self.animationSpeed = 1  # Default speed (0=slowest, 3=fastest)
        self.speedIntervals = [200, 100, 50, 25]  # Milliseconds between frames for each speed
        
        # Modifiable buttons
        self.nModPushButtons = 12
        self.modPushButtonDict = dict(zip(range(self.nModPushButtons),
                                          [['Mod-Button%d'%(i),dummyModButtonAction] for i in range(1,self.nModPushButtons+1)]))
        
        # Set default customized buttons (can be overridden by subclasses)
        self._setupDefaultButtons()
        
        self.VERBOSE = VERBOSE
        
        # Initialize markups
        self.Markups = tuiMarkups.Markups(self)
        self.markupActorList = []
        self.nSplinePoints = 100

    def _setupDefaultButtons(self):
        """Setup default customized buttons that can be overridden by subclasses"""
        self.modPushButtonDict = {
            0: ['Save points', self._defaultSavePoints],
            1: ['Save line', self._defaultSaveLine],
            2: ['Save VOI', self._defaultSaveVOI],
            3: ['Clear Markups', self._defaultClearMarkups],
        }

    def _defaultSavePoints(self):
        """Default save points action"""
        try:
            fOut = self.savePoints()
            if fOut and self.VERBOSE:
                print(f"Written points to {fOut}")
        except Exception as e:
            print(f"Error saving points: {e}")

    def _defaultSaveLine(self):
        """Default save line action"""
        try:
            fOut = self.saveLine()
            if fOut and self.VERBOSE:
                print(f"Written line to {fOut}")
        except Exception as e:
            print(f"Error saving line: {e}")

    def _defaultSaveVOI(self):
        """Default save VOI action"""
        try:
            fOut = self.saveVOI()
            if fOut and self.VERBOSE:
                print(f"Written VOI to {fOut}")
        except Exception as e:
            print(f"Error saving VOI: {e}")

    def _defaultClearMarkups(self):
        """Default clear markups action"""
        self.deleteAllMarkups()
        if self.VERBOSE:
            print("All markups cleared")

    def savePoints(self, featureName=None, prefix='pt'):
        """Save points as polydata"""
        try:
            ppDict = self.getMarkupAsPolydata()
            return self._save(ppDict, featureName=featureName, prefix=prefix)
        except Exception as e:
            print(f"Error in _savePoints: {e}")
            return None

    def saveLine(self, featureName=None, LINE_LOOP=False, prefix='line'):
        """Save line as polydata"""
        try:
            lineDict = self.getMarkupAsPolydata_lines(LINE_LOOP=LINE_LOOP)
            return self._save(lineDict, featureName=featureName, prefix=prefix)
        except Exception as e:
            print(f"Error in _saveLine: {e}")
            return None

    def saveVOI(self, featureName=None, prefix='fov'):
        """Save VOI as polydata"""
        try:
            ptsDict = self.getMarkupAsPolydata()
            voiDict = {}
            for iTime in ptsDict.keys():
                voiDict[iTime] = vtkfilters.getOutline(ptsDict[iTime])
            return self._save(voiDict, featureName=featureName, prefix=prefix)
        except Exception as e:
            print(f"Error in _saveVOI: {e}")
            return None

    def getMarkupAsPolydata(self):
        """Get markups as polydata dictionary"""
        outDict = {}
        try:
            for k1 in range(len(self.times)):
                if self.markupMode == 'Spline':
                    pp = self.Markups.getSplinePolyData(timeID=k1, nSplinePts=self.nSplinePoints)
                else:
                    pp = self.Markups.getPolyPointsFromPoints(timeID=k1)
                if pp.GetNumberOfPoints() > 0:
                    outDict[self.times[k1]] = pp
        except (AttributeError, ValueError) as e:
            if self.VERBOSE:
                print(f"Error getting markup polydata: {e}")
        return outDict

    def getMarkupAsPolydata_lines(self, LINE_LOOP=False):
        try:
            if self.markupMode == 'Spline':
                lineDict = self.getMarkupAsPolydata()
            else:
                ptsDict = self.getMarkupAsPolydata()
                lineDict = {}
                for iTime in ptsDict.keys():
                    lineDict[iTime] = vtkfilters.buildPolyLineFromXYZ(vtkfilters.getPtsAsNumpy(ptsDict[iTime]), LOOP=LINE_LOOP or self.splineClosed)
            return lineDict
        except Exception as e:
            print(f"Error in getMarkupAsPolydata_lines: {e}")
            return None

    def _save(self, polyDataDict, featureName=None, prefix='', extn='vtp', FORCE_PVD_EVEN_IF_SINGLE=False):
        """Save polydata dictionary to files"""
        if polyDataDict is None or len(polyDataDict) == 0:
            if self.VERBOSE:
                print("No data to save")
            return None
            
        if featureName is None:
            featureName = dialogGetName(self)
        if not featureName: # If user cancels
            return None
        try:
            if len(polyDataDict) == 1 and not FORCE_PVD_EVEN_IF_SINGLE:
                fileOut = self.getFullFileName(fileName=featureName, prefix=prefix, extn=extn)
                fileOut = fIO.writeVTKFile(polyDataDict[self.times[0]], fileOut)
            else:
                fileOut = fIO.writeVTK_PVD_Dict(polyDataDict, 
                                    rootDir=self.getWorkingDirectory(), 
                                    filePrefix=prefix+featureName, fileExtn=extn)
            return fileOut
        except Exception as e:
            print(f"Error saving file: {e}")
            return None

    def getFileNameViaDialog(self):
        """Get filename via dialog"""
        try:
            from PyQt5 import QtWidgets
            fileName, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save File", self.getWorkingDirectory(), 
                "VTK Files (*.vtp);;All Files (*)")
            return fileName if fileName else ""
        except Exception as e:
            if self.VERBOSE:
                print(f"Error getting filename: {e}")
            return ""

    def getFullFileName_interactive(self, fileName=None, prefix=None, extn=None):
        """Get full filename with prefix and extension"""
        if fileName is None:
            fileName = self.getFileNameViaDialog()
        if not fileName:
            return ""
        if prefix and not fileName.startswith(prefix):
            fileName = prefix + fileName
        if extn and not extn.startswith('.'):
            extn = '.' + extn
        if extn and not fileName.endswith(extn):
            fileName = fileName + extn
        return fileName


    def getFullFileName(self, fileName=None, prefix=None, extn=None):
        if fileName is None:
            fileName = dialogGetName(self)
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
        return os.path.join(str(self.workingDir), fileName)

    def getWorkingDirectory(self):
        """Get working directory"""
        try:
            if hasattr(self, 'workingDirLineEdit') and self.workingDirLineEdit:
                text = str(self.workingDirLineEdit.text())
                if text:
                    return text
            # Fallback to workingDir attribute or current directory
            if hasattr(self, 'workingDir') and self.workingDir:
                return self.workingDir
            return os.getcwd()
        except Exception:
            return os.getcwd()

    def __setScalarRangeForCurrentArray(self):
        """Set scalar range for current array"""
        sR_t = [self.vtiDict[iT].GetScalarRange() for iT in self.times]
        self.scalarRange[self.currentArray] = [min([i[0] for i in sR_t]), max([i[1] for i in sR_t])]
    
    def __calculateOptimalWindowLevel(self, arrayName=None):
        """Calculate optimal window level using percentile-based approach"""
        if arrayName is None:
            arrayName = self.currentArray
            
        if arrayName not in self.scalarRange:
            self.__setScalarRangeForCurrentArray()
            
        # Get the current VTI object
        vtiObj = self.getCurrentVTIObject()
        
        try:
            # Get the array data as numpy array for percentile calculation
            arrayData = vtkfilters.getArrayAsNumpy(vtiObj, arrayName)
            
            if arrayData is not None and arrayData.size > 0:
                # Calculate 2nd and 98th percentiles to exclude extreme outliers
                p2 = np.percentile(arrayData, 2)
                p98 = np.percentile(arrayData, 98)
                
                # Use percentile range for window width
                windowWidth = p98 - p2
                # Center the window level
                windowLevel = (p2 + p98) / 2.0
                
                if self.VERBOSE:
                    print(f"Optimal window level (percentile-based): window={windowWidth:.2f}, level={windowLevel:.2f}")
                    print(f"Data range: {np.min(arrayData):.2f} to {np.max(arrayData):.2f}")
                    print(f"Percentile range: {p2:.2f} to {p98:.2f}")
                
                return windowWidth, windowLevel
        except Exception as e:
            if self.VERBOSE:
                print(f"Error calculating optimal window level: {e}")
        
        # Fallback to simple range-based calculation
        sR = self.scalarRange.get(arrayName, [0, 255])
        dataMin, dataMax = sR[0], sR[1]
        dataRange = dataMax - dataMin
        
        if dataRange > 0:
            windowWidth = dataRange * 0.8
            windowLevel = (dataMin + dataMax) / 2.0
        else:
            windowWidth = 255
            windowLevel = dataMin
            
        return windowWidth, windowLevel

    def resetWindowLevel(self):
        """Reset window level to optimal values"""
        # Use the optimal window level calculation
        windowWidth, windowLevel = self.__calculateOptimalWindowLevel()
        
        if self.VERBOSE:
            print(f"Resetting window level: window={windowWidth:.2f}, level={windowLevel:.2f}")
        
        self._updateMarkups(window=windowWidth, level=windowLevel)

    def updatePushButtonDict(self, newPushButtonDict=None):
        """
        Update the modifiable push buttons with new actions and labels.

        This method allows customised buttons to be applied for the UI. 
        It updates the dictionary of modifiable push buttons with new
        actions and labels. It then applies these changes to the UI, enabling
        or disabling buttons as necessary.

        Args:
            newPushButtonDict (dict, optional): A dictionary containing new button
                configurations. The keys are button indices (0-11), and the values
                are lists containing the button label and the action to be performed
                when clicked. If None, the existing modPushButtonDict is used.

        Example:
            newDict = {
                0: ['Do Action A', action_function_A],
                1: ['Do Action B', action_function_B]
            }
            self.updatePushButtonDict(newDict)
        """
        if type(newPushButtonDict) == dict:
            self.modPushButtonDict = newPushButtonDict
        ### Modifiable push buttons
        if hasattr(self, 'modPushButtons'):
            for k1 in range(self.nModPushButtons):
                try:
                    self.modPushButtons[k1].setText(self.modPushButtonDict[k1][0])
                except KeyError:
                    self.modPushButtons[k1].setEnabled(False)
                    continue
                try:
                    self.modPushButtons[k1].clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.modPushButtons[k1].clicked.connect(self.modPushButtonDict[k1][1])
                self.modPushButtons[k1].setEnabled(True)
                if self.modPushButtonDict[k1][1] == dummyModButtonAction:
                    self.modPushButtons[k1].setEnabled(False)

    def setUserDefinedKeyPress(self, newKeyPressDict=None):
        """Set user-defined key press callbacks"""
        if hasattr(self, 'interactorStyleDict') and 'Image' in self.interactorStyleDict:
            self.interactorStyleDict['Image'].setUserDefinedKeyCallbackDict(newKeyPressDict)

    def getCurrentInteractorStyle(self):
        """Get current interactor style"""
        if hasattr(self, 'graphicsViewVTK'):
            return self.graphicsViewVTK.GetInteractorStyle()
        return None

    # TIME SLIDER
    def setupTimeSlider(self):
        """Setup time slider"""
        if hasattr(self, 'timeSlider'):
            self.timeSlider.setMinimum(0)
            self.timeSlider.setMaximum(len(self.times)-1)
            self.updateTimeLabel()

    def updateTimeLabel(self):
        """Update time label display"""
        if not hasattr(self, 'timeLabel') or not hasattr(self, 'timeSlider'):
            return
        try:
            self.timeLabel.setText("%d/%d [%3.2f]"%(self.currentTimeID+INDEX_OFFSET,
                                                          self.timeSlider.maximum()+INDEX_OFFSET,
                                                          self.getCurrentTime()))
        except IndexError:
            self.timeLabel.setText("%d/%d [%3.2f]"%(self.currentTimeID+INDEX_OFFSET,
                                                          self.timeSlider.maximum(),
                                                          0.0))

    def moveTimeSlider(self, val):
        """Move time slider to new value"""
        self.currentTimeID = val
        self.updateTimeLabel()
        self.updateViewAfterTimeChange()
        if hasattr(self, 'timeSlider'):
            self.timeSlider.setValue(self.currentTimeID)
        self._updateMarkups()

    def timeAdvance1(self):
        """Advance one time step"""
        if hasattr(self, 'timeSlider') and self.currentTimeID < (self.timeSlider.maximum()):
            self.currentTimeID += 1
        self.moveTimeSlider(self.currentTimeID)

    def timeReverse1(self):
        """Reverse one time step"""
        if hasattr(self, 'timeSlider') and self.currentTimeID > (self.timeSlider.minimum()):
            self.currentTimeID -= 1
        self.moveTimeSlider(self.currentTimeID)

    # ANIMATION FUNCTIONALITY
    def toggleAnimation(self):
        """Toggle animation play/pause"""
        if self.isAnimating:
            self.stopAnimation()
        else:
            self.startAnimation()

    def startAnimation(self):
        """Start the animation loop"""
        if len(self.times) <= 1:
            if self.VERBOSE:
                print("Cannot animate: only one time step available")
            return
            
        self.isAnimating = True
        if hasattr(self, 'playPauseButton'):
            self.playPauseButton.setText("Pause")
            self.playPauseButton.setChecked(True)
        
        # Create timer if it doesn't exist
        if self.animationTimer is None:
            from PyQt5.QtCore import QTimer
            self.animationTimer = QTimer()
            self.animationTimer.timeout.connect(self.animateNextFrame)
        
        # Set timer interval based on current speed
        interval = self.speedIntervals[self.animationSpeed]
        self.animationTimer.start(interval)
        
        if self.VERBOSE:
            print(f"Animation started at speed {self.animationSpeed} (interval: {interval}ms)")

    def stopAnimation(self):
        """Stop the animation"""
        self.isAnimating = False
        if hasattr(self, 'playPauseButton'):
            self.playPauseButton.setText("Play")
            self.playPauseButton.setChecked(False)
        
        if self.animationTimer:
            self.animationTimer.stop()
        
        if self.VERBOSE:
            print("Animation stopped")

    def animateNextFrame(self):
        """Move to next frame in animation loop"""
        if not self.isAnimating:
            return
            
        # Move to next time step
        if self.currentTimeID < len(self.times) - 1:
            self.currentTimeID += 1
        else:
            # Loop back to beginning
            self.currentTimeID = 0
        
        # Update the display
        self.moveTimeSlider(self.currentTimeID)

    def setAnimationSpeed(self, speed):
        """Set animation speed (0=slowest, 3=fastest)"""
        self.animationSpeed = speed
        
        # Update timer interval if animation is running
        if self.isAnimating and self.animationTimer:
            interval = self.speedIntervals[speed]
            self.animationTimer.start(interval)
        
        if self.VERBOSE:
            speedNames = ["Slowest", "Slow", "Fast", "Fastest"]
            print(f"Animation speed set to: {speedNames[speed]} (interval: {self.speedIntervals[speed]}ms)")

    # MARKUP MODE CONTROLS
    def markupModeChanged(self, mode):
        """Handle markup mode change"""
        self.markupMode = mode
        if self.VERBOSE:
            print(f"Markup mode changed to: {mode}")

    def splineClosedChanged(self, state):
        """Handle spline closed setting change"""
        self.splineClosed = state == 2  # Qt.Checked = 2
        if self.VERBOSE:
            print(f"Spline closed setting changed to: {self.splineClosed}")

    # DATA ACCESS METHODS
    def getCurrentTime(self):
        """Get current time value"""
        return self.times[self.currentTimeID]
    
    def getCurrentSliceID(self):
        """Get current slice ID - to be overridden by subclasses"""
        return 0  # Default for 3D viewer

    def getCurrentVTIObject(self, COPY=False):
        """Get current VTI object"""
        ii = self.vtiDict[self.getCurrentTime()]
        if COPY:
            i2 = vtk.vtkImageData()
            i2.ShallowCopy(ii)
            return i2
        return ii

    def selectArrayComboBoxActivated(self, selectedText):
        """Handle array selection change"""
        for iTime in self.times:
            self.vtiDict[iTime].GetPointData().SetActiveScalars(selectedText)
        self.updateViewAfterTimeChange()
        self.resetWindowLevel()
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(selectedText)
        self.setCurrentArray(selectedText)

    def setCurrentArray(self, arrayName):
        """Set current array"""
        self.currentArray = arrayName
        if hasattr(self, 'selectArrayComboBox'):
            self.selectArrayComboBox.setCurrentText(arrayName)
        self.resetWindowLevel()
        if hasattr(self, 'renderWindow'):
            self.renderWindow.Render()

    
    # FILE LOADING METHODS
    def setWorkingDirectory(self, workingDir):
        """Set working directory"""
        self.workingDir = workingDir
        self.workingDirLineEdit.setText(workingDir)

    def selectWorkingDirectory(self):
        """Open directory selector and update working directory"""
        try:
            from PyQt5 import QtWidgets
            currentDir = self.getWorkingDirectory()
            dirName = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Select Working Directory", currentDir)
            if dirName:
                self.setWorkingDirectory(dirName)
                if self.VERBOSE:
                    print(f"Working directory set to: {dirName}")
        except Exception as e:
            print(f"Error selecting working directory: {e}")

    def _getFileViaDialog(self):
        """Get file via dialog"""
        if not hasattr(self, 'fileDialog') or not hasattr(self, 'workingDirLineEdit'):
            return ""
        fileName = self.fileDialog.getOpenFileName(self,
                                                ("Open image data"),
                                                str(self.workingDirLineEdit.text()),
                                                ("Image data (*.vti);;PVD(, *.pvd)"))[0]
        if self.VERBOSE:
            print(str(fileName))
        return str(fileName)

    def _getDirectoryViaDialog(self):
        """Get directory via dialog"""
        if not hasattr(self, 'fileDialog') or not hasattr(self, 'workingDirLineEdit'):
            return ""
        dirName = self.fileDialog.getExistingDirectory(self,
                                                ("Open dicom directory"),
                                                str(self.workingDirLineEdit.text()))
        if self.VERBOSE:
            print(str(dirName))
        return str(dirName)

    def _loadDicom(self):
        """Load DICOM data"""
        if self.VERBOSE:
            print('Load dicoms')
        dirName = self._getDirectoryViaDialog()
        self.loadDicomDir(dirName)

    def loadDicomDir(self, dicomDir):
        """Load DICOM directory"""
        dcmSeries = spydcmtk.dcmTK.DicomSeries.setFromDirectory(dicomDir)
        self.vtiDict = dcmSeries.buildVTIDict()
        if self.VERBOSE:
            print(f"Have VTI dict. Times (ms): {[int(i*1000.0) for i in sorted(self.vtiDict.keys())]}")
        self.setWorkingDirectory(os.path.split(dicomDir)[0])
        self._setupAfterLoad()

    def loadVTI_or_PVD(self, fileName=None):
        """Load VTI or PVD file"""
        if self.VERBOSE:
            print('Load VTI')
        if not fileName:
            fileName = self._getFileViaDialog()
        if len(fileName) > 0:
            self.vtiDict = fIO.readImageFileToDict(fileName)
            for iTime in self.vtiDict.keys():
                for iName in vtkfilters.getArrayNames(self.vtiDict[iTime]):
                    vtkfilters.setArrayDtype(self.vtiDict[iTime], iName, np.float64)
                vtkfilters.ensureScalarsSet(self.vtiDict[iTime])
            if self.VERBOSE:
                print('Data loaded...')
            self.setWorkingDirectory(os.path.split(fileName)[0])
            self._setupAfterLoad()

    def _setupAfterLoad(self):
        """Setup after data load - to be overridden by subclasses"""
        # Stop any running animation
        if self.isAnimating:
            self.stopAnimation()
            
        self.times = sorted(self.vtiDict.keys())
        self.patientMeta.initFromVTI(self.getCurrentVTIObject())
        # Reset Markups
        self.Markups.initForNewData(len(self.times))
        self.setupTimeSlider()
        
        # Setup array selection
        if hasattr(self, 'selectArrayComboBox'):
            self.selectArrayComboBox.clear()
            arrayName = vtkfilters.getScalarsArrayName(self.vtiDict[self.getCurrentTime()])
            if not arrayName:
                arrayName = vtkfilters.getArrayNames(self.vtiDict[self.getCurrentTime()])[0]
            self.currentArray = arrayName
            self.currentTimeID = 0
            for iArray in vtkfilters.getArrayNames(self.vtiDict[self.getCurrentTime()]):
                self.selectArrayComboBox.addItem(iArray)
            self.selectArrayComboBox.setCurrentText(self.currentArray)
        else:
            # Fallback if no combo box
            arrayName = vtkfilters.getScalarsArrayName(self.vtiDict[self.getCurrentTime()])
            if not arrayName:
                arrayName = vtkfilters.getArrayNames(self.vtiDict[self.getCurrentTime()])[0]
            self.currentArray = arrayName
            self.currentTimeID = 0
        
        # Calculate bounding distance
        bounds = self.getCurrentVTIObject().GetBounds()
        self.boundingDist = max([bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]])
        
        # Call subclass-specific setup
        self._setupViewerSpecificData()
        
        self.moveTimeSlider(self.currentTimeID)

    def _setupViewerSpecificData(self):
        """Override in subclasses for viewer-specific setup"""
        pass

    def _setupCommonConnections(self):
        """Setup common UI connections that both viewers share"""
        # Time slider connections
        if hasattr(self, 'timeSlider'):
            self.timeSlider.valueChanged.connect(self.moveTimeSlider)
            self.timeSlider.setSingleStep(1)
            self.timeSlider.setPageStep(5)
        
        # Array selection
        if hasattr(self, 'selectArrayComboBox'):
            self.selectArrayComboBox.activated[str].connect(self.selectArrayComboBoxActivated)
        
        # Menu actions
        if hasattr(self, 'actionQuit'):
            self.actionQuit.triggered.connect(self.exit)
        if hasattr(self, 'actionDicom'):
            self.actionDicom.triggered.connect(self._loadDicom)
        if hasattr(self, 'actionVTK_Image'):
            self.actionVTK_Image.triggered.connect(self.loadVTI_or_PVD)
        
        # Animation controls
        if hasattr(self, 'playPauseButton'):
            self.playPauseButton.clicked.connect(self.toggleAnimation)
        if hasattr(self, 'speedSlider'):
            self.speedSlider.valueChanged.connect(self.setAnimationSpeed)
        
        # Markup mode controls
        if hasattr(self, 'markupModeComboBox'):
            self.markupModeComboBox.currentTextChanged.connect(self.markupModeChanged)
        if hasattr(self, 'closedSplineCheck'):
            self.closedSplineCheck.stateChanged.connect(self.splineClosedChanged)
        
        # Help button
        if hasattr(self, 'helpButton'):
            self.helpButton.clicked.connect(self.showHelpWindow)

    # MARKUP METHODS
    def deleteAllMarkups(self):
        """Delete all markups"""
        self.Markups.reset()
        self._updateMarkups()

    def addPoint(self, X, norm=None):
        """Add a point markup"""
        self.Markups.addPoint(X, self.currentTimeID, self.getCurrentSliceID(), norm)
        self._updateMarkups()

    def removeLastPoint(self):
        """Remove last point"""
        self.Markups.removeLastPoint(self.currentTimeID)
        self._updateMarkups()

    def addPolydata(self, polydata, timeID=None, time=None, color=(0,1,1)):
        """Add polydata markup"""
        if time is not None:
            timeID = int(np.argmin([abs(i-time) for i in self.times]))
        else:
            if timeID is None:
                timeID = self.currentTimeID
        iTime = self.times[timeID]
        self.Markups.addPolydata(polydata, timeID, iTime, color=color)
        self._updateMarkups()

    def clearCurrentMarkups(self):
        """Clear current markup actors"""
        for iActor in self.markupActorList:
            self.removeActorFromAllRenderers(iActor)
        self.markupActorList = []

    def removeActorFromAllRenderers(self, actor):
        """Remove actor from all renderers - to be overridden by subclasses"""
        pass

    def _updateMarkups(self, window=None, level=None):
        """Update markup display - to be overridden by subclasses"""
        pass

    def updateViewAfterTimeChange(self):
        """Update view after time change - to be overridden by subclasses"""
        pass

    def getWindowLevel(self):
        """Get window level - to be overridden by subclasses"""
        return 255, 127.5

    def setWindowLevel(self, w, l):
        """Set window level - to be overridden by subclasses"""
        pass
    
    # CAMERA METHODS
    def cameraReset(self):
        """Reset camera to default position - to be overridden by subclasses"""
        pass
    
    def cameraReset3D(self):
        """Reset 3D camera clipping range - to be overridden by subclasses"""
        pass
    
    # COORDINATE CONVERSION METHODS
    def getPointIDAtX(self, X):
        """Get point ID from world coordinates - to be overridden by subclasses"""
        return self.getCurrentVTIObject().FindPoint(X)
    
    def getIJKAtX(self, X):
        """Convert world coordinates to IJK coordinates - to be overridden by subclasses"""
        ijk = [0, 0, 0]
        pcoords = [0.0, 0.0, 0.0]
        res = self.getCurrentVTIObject().ComputeStructuredCoordinates(X, ijk, pcoords)
        if res == 0:
            return None
        return ijk
    
    def getIJKAtPtID(self, ptID):
        """Get IJK coordinates from point ID - to be overridden by subclasses"""
        X = self.getCurrentVTIObject().GetPoint(ptID)
        return self.getIJKAtX(X)
    
    def getPixelValueAtPtID_tuple(self, ptID):
        """Get pixel value tuple from point ID - to be overridden by subclasses"""
        if (ptID < 0) or (ptID >= self.getCurrentVTIObject().GetNumberOfPoints()):
            return None
        return self.getCurrentVTIObject().GetPointData().GetArray(self.currentArray).GetTuple(ptID)
    
    def imageCS_To_WorldCS_X(self, imageCS_X):
        """Convert image coordinates to world coordinates - to be overridden by subclasses"""
        # Default implementation - subclasses should override with proper coordinate system handling
        return imageCS_X
    
    def getCurrentViewNormal(self):
        """Get current view normal - to be overridden by subclasses"""
        return np.array([0, 0, 1])  # Default Z-axis normal
    
    def getViewNormal(self, i):
        """Get view normal for view i - to be overridden by subclasses"""
        return self.getCurrentViewNormal()
    
    # RENDERING METHODS
    def updateViewAfterSliceChange(self):
        """Update view after slice change - to be overridden by subclasses"""
        pass
    
    # COMMON INITIALIZATION METHODS
    def _setupVTKInteractor(self, graphicsView):
        """Setup common VTK interactor initialization"""
        try:
            self.graphicsViewVTK = QVTKRenderWindowInteractor(graphicsView)
        except AttributeError:
            self.graphicsViewVTK = QVTKRenderWindowInteractor(self.widget)  # vtkRenderWindowInteractor
        
        self.graphicsViewVTK.setObjectName("graphicsView")
        self.graphicsViewVTK.RemoveObservers("KeyPressEvent")
        self.graphicsViewVTK.RemoveObservers("CharEvent")
        
        # Import QtWidgets here to avoid circular imports
        from PyQt5 import QtWidgets
        layout = QtWidgets.QVBoxLayout(graphicsView)
        layout.addWidget(self.graphicsViewVTK)
        graphicsView.setLayout(layout)
        
        self.renderWindow = self.graphicsViewVTK.GetRenderWindow()
        self.renderWindow.SetMultiSamples(0)
        
        self.graphicsViewVTK.Initialize()
        self.graphicsViewVTK.Start()
        
        return self.graphicsViewVTK, self.renderWindow

    def showHelpWindow(self):
        """Show help window with keyboard shortcuts and interaction guide"""
        # Import here to avoid circular imports
        from PyQt5 import QtWidgets
        
        help_window = QtWidgets.QDialog(self)
        help_window.setWindowTitle("TUI Help")
        help_window.setModal(False)
        help_window.resize(500, 600)
        
        layout = QtWidgets.QVBoxLayout(help_window)
        
        # Help text
        help_text = QtWidgets.QTextEdit()
        help_text.setReadOnly(True)
        
        # Read base help content from file
        help_content = self._loadHelpContent()
        
        # Allow subclasses to append custom help
        custom_help = self._getCustomHelp()
        if custom_help:
            help_content += "\n\n" + custom_help
        
        # Convert to HTML for nicer formatting
        html_content = self._formatHelpAsHTML(help_content)
        help_text.setHtml(html_content)
        layout.addWidget(help_text)
        
        # Close button
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(help_window.accept)
        layout.addWidget(close_button)
        
        help_window.show()

    def _loadHelpContent(self):
        """Load help content from help file"""
        import os
        help_file = os.path.join(os.path.dirname(__file__), self._getHelpFileName())
        try:
            with open(help_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"Help file not found. Please ensure {self._getHelpFileName()} exists in the tui directory."
        except Exception as e:
            return f"Error loading help file: {str(e)}"

    def _getHelpFileName(self):
        """Override this method in subclasses to specify different help files"""
        return "help.txt"

    def _getCustomHelp(self):
        """Override this method in subclasses to add custom help content
        
        Example usage in a subclass:
        
        class MyCustomTUIViewer(TUIMarkupViewer):
            def _getCustomHelp(self):
                return '''CUSTOM FEATURES:
• F1 - My custom feature 1
• F2 - My custom feature 2
• Custom button - Does something special'''
        """
        return ""

    def _formatHelpAsHTML(self, text_content):
        """Convert plain text help content to nicely formatted HTML"""
        import re
        
        # Start with HTML structure
        html = """
        <html>
        <head>
        <style>
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            font-size: 11px; 
            line-height: 1.4; 
            margin: 10px;
            background-color: #f8f9fa;
        }
        h1 { 
            color: #2c3e50; 
            font-size: 16px; 
            font-weight: bold; 
            margin: 0 0 15px 0; 
            padding-bottom: 5px;
            border-bottom: 2px solid #3498db;
        }
        h2 { 
            color: #34495e; 
            font-size: 13px; 
            font-weight: bold; 
            margin: 15px 0 8px 0; 
            background-color: #ecf0f1;
            padding: 5px 8px;
            border-left: 4px solid #3498db;
        }
        ul { 
            margin: 5px 0; 
            padding-left: 0;
        }
        li { 
            margin: 3px 0; 
            padding: 2px 0;
            list-style: none;
        }
        li:before { 
            content: "• "; 
            color: #3498db; 
            font-weight: bold; 
            margin-right: 5px;
        }
        .keyboard { 
            background-color: #e8f4fd; 
            padding: 2px 6px; 
            border-radius: 3px; 
            font-family: 'Courier New', monospace; 
            font-weight: bold;
            color: #2980b9;
        }
        .description { 
            color: #555; 
        }
        </style>
        </head>
        <body>
        """
        
        # Split content into lines
        lines = text_content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if not line:
                html += "<br/>"
                continue
            
            # Check if it's a main title (no bullet point)
            if line and not line.startswith('•') and not line.startswith('*'):
                if ':' in line and not line.startswith(' '):
                    # It's a section header
                    html += f"<h2>{line}</h2>"
                else:
                    # It's a main title
                    html += f"<h1>{line}</h1>"
            else:
                # It's a bullet point
                if line.startswith('•'):
                    line = line[1:].strip()
                elif line.startswith('*'):
                    line = line[1:].strip()
                
                # Look for keyboard shortcuts (text before first dash)
                if ' - ' in line:
                    parts = line.split(' - ', 1)
                    if len(parts) == 2:
                        key_part = parts[0].strip()
                        desc_part = parts[1].strip()
                        
                        # Format keyboard shortcuts
                        if any(char in key_part for char in ['•', 'h', '.', 'u', 'r', 'R', '1', '2', '3', '4', '5', 'p', 'm', 'c', 'o', 'l', 'w', 'V']):
                            html += f"<li><span class='keyboard'>{key_part}</span> - <span class='description'>{desc_part}</span></li>"
                        else:
                            html += f"<li><span class='keyboard'>{key_part}</span> - <span class='description'>{desc_part}</span></li>"
                    else:
                        html += f"<li>{line}</li>"
                else:
                    html += f"<li>{line}</li>"
        
        html += "</body></html>"
        return html

    def exit(self):
        """Exit application"""
        self.close()
        return 0


def dummyModButtonAction():
    """Dummy action for unused buttons"""
    print('Nothing implemented')
