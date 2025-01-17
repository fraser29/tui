# tui

**TUI** a beautiful NZ native bird - but also a technical user interfacce. 

This is a fairly basic UI designed for medical image analysis. 
It leverages mostly VTK and permits powerful customisation of buttons / keyboard shortcuts etc to allow rapid markup of data.
This permits high efficiency for medical imaging projects.  

**TUI** provides a 4D viewer (volume + time). 

Volume viewer is by way of a 3-plane orthogonal viewer allowing double oblique slice positioning. 

A basic 3D viewer for surface rendering is also included. 

**TUI** is an excellent option for: 
- basic markup for project work
- development and testing of segmentation algorithms
- inspection of medical imaging data. 

## Format

**TUI** will read: 
- dicom files
- VTK image data (vti)
- MHA
- Nifti

Internal format used is VTK image data. 

## Why TUI

A major distinction from Slicer3D/MITK etc is simplicity and simple customisation. 

If you have a work flow to apply to your study images, then this application will allow you to quickly set buttons and shortcuts to achieve this. 


# TODO

3D window in new thread with update button

Dicom exporter.

Orthogonal slice aligner

Measurement