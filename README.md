# tui

**TUI** a beautiful NZ native bird - but also a technical user interfacce. 

This is a fairly basic UI designed for medical image analysis. 
It leverages mostly VTK and permits powerful customisation of buttons / keyboard shortcuts etc to allow rapid markup of data.
This permits high efficiency for medical imaging projects.  

**TUI** provides a 4D viewer (volume + time). 

Volume viewer is by way of a 3-plane orthogonal viewer allowing double oblique slice positioning. A basic 3D viewer for surface rendering is also included in a 4th panel. 

A complementary application (**piwakwaka** use the "-2D" option at commandline) is provided for viewing image slices (acquired "axial", "sagittal", "coronal" - i.e. no oblique slicing)

**TUI** is an excellent option for: 
- basic markup for project work
    - if you need to mark 500 aorta centerlines, just set a keyboard shortcut to save as "Subj*_AoCL.vtp" and save yourself typing that 500 times. 
- development and testing of segmentation algorithms
- inspection of medical imaging data. 

## Format

**TUI** will read: 
- dicom files
- VTK image data (vti)
- MHA
- Nifti
- Analyze

Internal format used is VTK image data. 

## Why TUI

A major distinction from Slicer3D/MITK etc is simplicity and simple customisation. 

If you have a work flow to apply to your study images, then this application will allow you to quickly set buttons and shortcuts to achieve this. 


