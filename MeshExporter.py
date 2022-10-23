# Creates seperate meshes from joint info

from pickle import TRUE
import adsk.core, adsk.fusion

from . import UnityExporter

rootComp = None
app = None
ui = adsk.core.UserInterface.cast(None)

jointOccs = {}
newTransform = None

# Recursively finds grounded comps
def findGroundOccs(occurrences):
    groundedOccs = []

    for i in range(0, occurrences.count):
        occ = occurrences[i]
        if occ.isGrounded:
            groundedOccs.append(occ)
        if occ.childOccurrences:
            groundedOccs.extend(findGroundOccs(occ.childOccurrences))

    return groundedOccs

# Recursively travels through assemblies and stores all assemblies with joint info
def findJointAssemblies(occurrences):
    assemblyOcc = []

    for i in range(0, occurrences.count):
        occ = occurrences.item(i)

        # Breaks Links to be able to edit comps freely
        if occ.isReferencedComponent:
            occ.breakLink()

        if occ.childOccurrences:
            # If has Joints, add
            if occ.component.joints.count > 0 or occ.component.rigidGroups.count > 0:
                assemblyOcc.append(occ)
                # Locks Joints
                for joint in occ.component.joints:
                    if joint.jointMotion.jointType != 0:
                        joint.isLocked = True
            
            # Nested Search
            newOcc = findJointAssemblies(occ.childOccurrences)
            for o in newOcc:
                assemblyOcc.append(o)

    return assemblyOcc

# Recursively travels through assemblies deleting small bodies
def removeSmallInAssembly(baseSize, occurrences):
    for occ in occurrences:
        
        volume = occ.component.physicalProperties.volume
        if volume < 1.5 and volume < baseSize / 2:
            occ.isLightBulbOn = False

        elif occ.childOccurrences:
                removeSmallInAssembly(baseSize, occ.childOccurrences)

# Return Origin of Joint in World Space
def jointOriginWorldSpace(jointObj):
    jointsOcc = jointObj.occurrenceTwo
    if not jointsOcc:
        jointsOcc = rootComp
    # Sets Correct Origin Based on Occurrence not Component (Also only 1 origin for offset purposes)
    try:
        joint = jointObj.geometryOrOriginTwo
    except: # May not have geometryTwo
        jointsOcc = jointObj.occurrenceOne
        joint = jointObj.geometryOrOriginOne
    app.activeViewport.refresh()
    if joint.objectType == adsk.fusion.JointOrigin.classType():
        joint = joint.geometry
    jointsOrigin = joint.origin
    try:
        if joint.entityOne.objectType == adsk.fusion.ConstructionPoint.classType():
            baseComp = joint.entityOne.component
        elif joint.entityOne.objectType == adsk.fusion.SketchPoint.classType():
            baseComp = rootComp
        else:
            baseComp = joint.entityOne.body.parentComponent
    except:
        ui.messageBox("Whoops! It seems Joint: \"" + jointObj.name + "\" is connected to a currently not supported piece of Geometry! In a future update this may be fixed.")
        joint.entityOne.body.parentComponent
    baseComp = rootComp.allOccurrencesByComponent(baseComp).item(0)
    if baseComp:
        transform = baseComp.transform2
        transform.invert()
        transform.transformBy(jointsOcc.transform2)
        jointsOrigin.transformBy(transform)
    return jointsOrigin

# Returns vector with only one +/- 1 value
def returnNormalVector(point):
    if abs(point.x) > abs(point.y) and abs(point.x) > abs(point.z):
        returnVec = adsk.core.Vector3D.create(1, 0, 0)
        returnVec.scaleBy(point.x / abs(point.x))
        return returnVec
    if abs(point.y) > abs(point.x) and abs(point.y) > abs(point.z):
        returnVec = adsk.core.Vector3D.create(0, 1, 0)
        returnVec.scaleBy(point.y / abs(point.y))
        return returnVec
    if abs(point.z) > abs(point.x) and abs(point.z) > abs(point.y):
        returnVec = adsk.core.Vector3D.create(0, 0, 1)
        returnVec.scaleBy(point.z / abs(point.z))
        return returnVec

# Rigid Combination
def rigidOccs(occs, assembledComps, _assembledComps, groundedComps, exportComp):
    # New Component per Rigid Joint or absorb into other Group
    newCompNames = []
    grounded = False
    for occRG in occs:
        if occRG in groundedComps:
            grounded = True
        for i in range(len(assembledComps)):
            # If Comp Already in Link, Absorb Previous Linked Components into One
            if occRG.fullPathName in assembledComps[i]:
                if i == 0:
                    grounded = True
                    break
                for compName in assembledComps[i]:
                    newCompNames.append(compName)
                assembledComps[i] = []
                _assembledComps[i].deleteMe()
                break
        # Else, Create Link for New Component
        else:
            newCompNames.append(occRG.fullPathName)
    # Stores Linked info into Arrays
    if grounded:
        assembledComps[0].extend(newCompNames)
    else:
        newComp = exportComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        newComp.component.name = "unitycomp_" + str(len(assembledComps))
        assembledComps.append(newCompNames)
        _assembledComps.append(newComp)
    return assembledComps, _assembledComps


# Main Function
def runMesh(wheelNames):
    global app, ui

    app = adsk.core.Application.get()
    ui = app.userInterface

    # Get the root component of the active design
    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    global rootComp
    rootComp = design.rootComponent
    app.activeViewport.refresh()

    # Creates Progress Bar
    progressBar = ui.createProgressDialog()


    # Leave this here in case I need to debug again

    # Create a graphics group on the root component.
    #graphics = rootComp.customGraphicsGroups.add()
    # Adds Point Graphic
    #coord = adsk.fusion.CustomGraphicsCoordinates.create(point.asArray())
    #point = graphics.addPointSet(coord, [0], adsk.fusion.CustomGraphicsPointTypes.UserDefinedCustomGraphicsPointType,
    #    'SelectJoint.png')


    # Checks upwards and forward directions
    progressBar.show("Converting Robot File", "Starting Process...", 0, 1, 0)
    progressBar.progressValue = 1
    app.activeViewport.refresh()
    adsk.doEvents()
    originalCam = app.activeViewport.camera
    # Move to Up
    cam = app.activeViewport.camera
    cam.viewOrientation = 10
    cam.isSmoothTransition = False
    app.activeViewport.camera = cam
    app.activeViewport.fit()
    # Capture Up
    cam = app.activeViewport.camera
    yVector = returnNormalVector(cam.eye)
    # Move to Forward
    cam.viewOrientation = 3
    cam.isSmoothTransition = False
    app.activeViewport.camera = cam
    app.activeViewport.fit()
    # Capture Forward
    cam = app.activeViewport.camera
    zVector = returnNormalVector(cam.eye)
    # Reset
    app.activeViewport.camera = originalCam
    app.activeViewport.fit()
    # Gets Transform to apply to occurrences
    global newTransform
    newTransform = adsk.core.Matrix3D.create()
    origin = adsk.core.Point3D.create(0, 0, 0)
    newTransform.setToAlignCoordinateSystems(origin, yVector.crossProduct(zVector), yVector, zVector, origin,
        adsk.core.Vector3D.create(-1, 0, 0), adsk.core.Vector3D.create(0, 1, 0), adsk.core.Vector3D.create(0, 0, -1))
    # Adds on origin as well
    minPoint = rootComp.boundingBox.minPoint.asVector()
    maxPoint = rootComp.boundingBox.maxPoint.asVector()
    minPoint.transformBy(newTransform)
    maxPoint.transformBy(newTransform)
    floorPoint = min(minPoint.y, maxPoint.y)
    minPoint.add(maxPoint)
    minPoint.scaleBy(-.5)
    minPoint.y = -floorPoint #Ground Plane is offset weirdly so base it instead off of wheel sizes in importer
    newTransform.setToAlignCoordinateSystems(origin, yVector.crossProduct(zVector), yVector, zVector, minPoint.asPoint(),
        adsk.core.Vector3D.create(-1, 0, 0), adsk.core.Vector3D.create(0, 1, 0), adsk.core.Vector3D.create(0, 0, -1))

    # Checks if any grounded comps
    groundedComps = findGroundOccs(rootComp.occurrences)

    # Creates List of assembly components that contain (locked) joints
    assemblyOcc = [rootComp]
    for joint in rootComp.joints:
        if joint.jointMotion.jointType != 0:
            joint.isLocked = True
    for occ in findJointAssemblies(rootComp.occurrences):
        assemblyOcc.append(occ)


    # -Loops through Joints in Assemblies-

    # Puts all in exportcomp to be able to re-orient unitycomps
    exportComp = rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create()).component
    exportComp.name = "exportcomps"
    # (First Assembled Group is Base Group)
    assembledComps = [[]]
    inverseTransform = newTransform.copy() # This is needed as basecomp refuses to be rotated
    inverseTransform.invert()
    _assembledComps = [exportComp.occurrences.addNewComponent(inverseTransform)]
    _assembledComps[0].component.name = "unitycomp_0"

    if progressBar.wasCancelled:
        return False
    progressBar.show("Converting Robot File", "Step 1: Analyzing Joint Data...", 0, len(assemblyOcc) * 4, 0)
    progressBar.progressValue = 0

    # Does Rigid Groups First
    for occs in assemblyOcc:
        occ = occs if occs == rootComp else occs.component
        for rg in occ.rigidGroups:
            if rg.isSuppressed:
                continue
            if occs != rootComp:
                rg = rg.createForAssemblyContext(occs)
            # Calls to modify assembledComps based off new occs
            assembledComps, _assembledComps = rigidOccs(rg.occurrences, assembledComps, _assembledComps, groundedComps, exportComp)
        if progressBar.wasCancelled:
            return False
        progressBar.progressValue += 1

    # Does Rigid Joints Next
    for occs in assemblyOcc:
        occ = occs if occs == rootComp else occs.component
        for rigidJoint in occ.joints:
            if rigidJoint.isSuppressed:
                continue
            # Joins Rigid Joint Components together
            if rigidJoint.jointMotion.jointType == 0:
                if occs != rootComp:
                    rigidJoint = rigidJoint.createForAssemblyContext(occs)
                jointsOcc = [rigidJoint.occurrenceOne, rigidJoint.occurrenceTwo]
                # Calls to modify assembledComps based off new occs
                assembledComps, _assembledComps = rigidOccs(jointsOcc, assembledComps, _assembledComps, groundedComps, exportComp)
        if progressBar.wasCancelled:
            return False
        progressBar.progressValue += 1

    # Does Revolve/Slide Joints Last
    childGroups = []
    jointPairs = []
    jntXMLS = []
    jointCount = 0
    for occs in assemblyOcc:
        occ = occs if occs == rootComp else occs.component
        for jointObj in occ.joints:
            if jointObj.isSuppressed:
                continue
            # Breaks up Joint Components into seperate assembledComps
            if jointObj.jointMotion.jointType == 1 or jointObj.jointMotion.jointType == 2:
                if occs != rootComp:
                    jointObj = jointObj.createForAssemblyContext(occs)
                # Creates an Unlinked Component for the Revolute Part
                occurrences = [jointObj.occurrenceOne, jointObj.occurrenceTwo]
                                    # --Can skip grounded check if no grounded comps--
                for jntOcc in range(2 if len(groundedComps) > 0 and occurrences[1] else 1):
                    if occurrences[jntOcc] == rootComp or occurrences[jntOcc] in groundedComps:
                        if jntOcc == 0:
                            childGroups.append(0)
                        else:
                            parentGroup = 0
                        continue
                    for i in range(len(assembledComps)):
                        if occurrences[jntOcc].fullPathName in assembledComps[i]:
                            if jntOcc == 0:
                                childGroups.append(i)
                            else:
                                parentGroup = i
                            break
                    else:
                        # Not a part of a section
                        if jntOcc == 0:
                            childGroups.append(len(assembledComps))
                        else:
                            parentGroup = len(assembledComps)
                        newOcc = exportComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
                        newOcc.component.name = "unitycomp_" + str(len(assembledComps))
                        assembledComps.append([occurrences[jntOcc].fullPathName])
                        _assembledComps.append(newOcc)
                # Setup Joint XML
                jntXMLS.append(UnityExporter.createJntXML(jointObj, parentGroup, childGroups[-1], jointCount))
                jointPairs.append([parentGroup, childGroups[-1]])
                jointCount += 1
        if progressBar.wasCancelled:
            return False
        progressBar.progressValue += 2

    # Need to do basejoint check if no grounded comp present
    groundedJnts = [0]
    # Check if already part of a grounded connection
    if len(groundedComps) > 0:
        i = 0
        while i < len(groundedJnts):
            for pair in jointPairs:
                if pair[0] == groundedJnts[i] and pair[1] not in groundedJnts:
                    groundedJnts.append(pair[1])
                elif pair[1] == groundedJnts[i] and pair[0] not in groundedJnts:
                    groundedJnts.append(pair[0])
            i += 1
    # For all groups not part of a grounded connection, ground loose parents of joints
    for i in range(1, len(assembledComps)):
        if i not in groundedComps and _assembledComps[i].isValid and i not in childGroups:
            assembledComps[i] = []
            _assembledComps[i].deleteMe()
    app.activeViewport.refresh()

    # Meshing Code
    progressBar.show("Converting Robot File", "Step 2: Combining Occurrences...", 0, len(assembledComps), 0)
    progressBar.progressValue = 0
    for i in range(1, len(assembledComps)):
        for c in range(len(assembledComps[i])):
            childOccs = rootComp.occurrences
            location = assembledComps[i][c].split('+')
            for occName in location:
                newOcc = childOccs.itemByName(occName)
                if not newOcc:
                    break
                childOccs = newOcc.childOccurrences
            if newOcc:
                # --WIP TEST--
                # If has children comps, don't also link them
                #if newOcc.childOccurrences:
                #    newComp = _assembledComps[i].component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
                #    for body in newOcc.bRepBodies:
                #        body.moveToComponent(newComp)
                # Link connected comp to assembledComp
                #else:
                newOcc.moveToComponent(_assembledComps[i])
            if progressBar.wasCancelled:
                return False
        progressBar.progressValue += 1
    while rootComp.occurrences.item(0).name != "exportcomps:1":
        rootComp.occurrences.item(0).moveToComponent(_assembledComps[0])
    progressBar.progressValue += 1

    # Removes Wheel Comps
    for wheel in wheelNames:
        for i in range(1, len(assembledComps)):
            if wheel in assembledComps[i]:
                _assembledComps[i].isLightBulbOn = False
                break

    # Remove Small Bodies
    progressBar.show("Converting Robot File", "Step 3: Removing Small Bodies...", 0, len(assembledComps), 0)
    progressBar.progressValue = 0
    for occ in rootComp.occurrences[0].childOccurrences: # _assembledComps couldnt tell if LightBulbOn
        if occ.isLightBulbOn:
            removeSmallInAssembly(occ.physicalProperties.volume, occ.childOccurrences)
        if progressBar.wasCancelled:
            return False
        progressBar.progressValue += 1

    progressBar.hide()
    return jntXMLS