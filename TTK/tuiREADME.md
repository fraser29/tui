# fdq markup

UI for FDQ Markup. 

## TASKS
* Load FDQ dataset (from dicoms or pvd)
* Reduce to VOI (draw fov)
* select static tissue
  1. auto algorithm
    - adjust air and velstdev sliders
  2. draw to exclude non-static tissue
* Choose MRAContour
* Define landmarks
  1. Build and track ROIs
  2. Build centerlines
  
## Advanced
* Track valves
* Segment ventricles

  
## Fastest work up:
* Manual CLs
* Manual LMs - auto MIP ROIs - to a segmentation
* Manual chamber isolation (manual ROIs with through plane)


## Final goal:
* CLs in major vessels with vec stats on all
  1. Interrogation interface
* Paths classified between major junctions:
  1. IVC/ SVC through to LPA / RPA
  2. All in between of above
  3. 4 PV throuh to AV
  4. AV to 3 branch + AoDsc
  5. **Shunts**
* Segmentation
* WSS
* Energy loss etc between major junctions
* Visulisation upon other CINEs etc.
* Pressure losses
* Main vessel recirc


