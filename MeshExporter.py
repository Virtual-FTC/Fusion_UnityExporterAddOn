# PHASE TWO SCRIPT - Creates reduced mesh from current robot file

from asyncio.windows_events import NULL
from email.mime import application, base
import os
from pickle import TRUE
from xml.dom import minidom
import adsk.core, adsk.fusion, traceback
from . import RobotConfig


# Recursively travels through assemblies and stores all assemblies with joint info
def findJointAssemblies(occurrences):
    assemblyOcc = []

    for i in range(0, occurrences.count):
        occ = occurrences.item(i)

        if occ.childOccurrences:
            if occ.component.joints.count > 0 or occ.component.rigidGroups.count > 0:
                assemblyOcc.append(occ)
            newOcc = findJointAssemblies(occ.childOccurrences)
            for o in newOcc:
                assemblyOcc.append(o)

    return assemblyOcc


'''
# Recursively travels through assemblies moving components to new _UnityComp_ Components
def traverseAssembly(occurrences, assembledComps, _assembledComps, progressBar, rootComp):
    if rootComp:
        progressBar.show("Converting Robot File", "Step 2: Combining Components...", 0, occurrences.count - len(assembledComps), 0)
        progressBar.progressValue = 0
        # Specific Loop for RootComp Bodies
        while rootComp.bRepBodies.count > 0:
            if rootComp.bRepBodies.item(0).volume > 1.5:
                rootComp.bRepBodies.item(0).copyToComponent(_assembledComps[0])
            rootComp.bRepBodies.item(0).deleteMe()
    # Loops through Occurrences
    o = 0
    while o < occurrences.count:
        occ = occurrences.item(o)

        if occ.name == "_UnityComp_0:1":
            return

        unityComp = _assembledComps[0]
        for i in range(1, len(assembledComps)):
            if occ.fullPathName in assembledComps[i]:
                unityComp = _assembledComps[i]
                break

        if occ.childOccurrences:
            traverseAssembly(occ.childOccurrences, assembledComps, _assembledComps, progressBar, None)

        for body in occ.bRepBodies:
            if body.volume > 1.5:
                body.copyToComponent(unityComp)

        if progressBar.wasCancelled:
            return

        # Updates List
        if rootComp:
            occ.deleteMe()
            occurrences = rootComp.occurrences.asList
            progressBar.progressValue += 1
        else:
            o += 1
'''

# Recursively travels through assemblies deleting small bodies
def removeSmallInAssembly(occurrences, progressBar, rootComp):
    for occ in occurrences:
        if occ.name == "base_link:1":
            return
        
        #box = occ.boundingBox
        #size = (box.maxPoint.x - box.minPoint.x) * (box.maxPoint.y - box.minPoint.y) * (box.maxPoint.z - box.minPoint.z)
        #if size < 7.5:
        #    occ.deleteMe()
        if occ.component.physicalProperties.volume < 1.5:
            occ.isLightBulbOn = False


        elif occ.childOccurrences:
                removeSmallInAssembly(occ.childOccurrences, None, rootComp)

        if progressBar:
            progressBar.progressValue += 1

'''
# Recursively travels through assemblies moving Occurrences to new _UnityComp_ Occurrences
def combineAssembly(occurrences, assembledComps, _assembledComps, progressBar, rootComp):
    if rootComp:
        # Specific Loop for RootComp Bodies
        while rootComp.bRepBodies.count > 0:
            if rootComp.bRepBodies.item(0).volume > 1.5:
                rootComp.bRepBodies.item(0).copyToComponent(_assembledComps[0])
            rootComp.bRepBodies.item(0).deleteMe()
    # Loops through Occurrences
    o = 0
    while o < occurrences.count:
        occ = occurrences.item(o)

        if occ.name == "_UnityComp_0:1":
            return

        unityComp = _assembledComps[0]
        for i in range(1, len(assembledComps)):
            if occ.fullPathName in assembledComps[i]:
                unityComp = _assembledComps[i]
                break

        if occ.childOccurrences and unityComp == _assembledComps[0]:
            combineAssembly(occ.childOccurrences, assembledComps, _assembledComps, progressBar, None)

        if rootComp or len(occ.fullPathName.split(":")) > 2:
            occ.nativeObject.moveToComponent(unityComp)
        else:
            return

        if progressBar.wasCancelled:
            return

        # Updates List
        if rootComp:
            occurrences = rootComp.occurrences.asList
            progressBar.progressValue += 1
'''

def runMesh():
    app = adsk.core.Application.get()
    ui = app.userInterface


    # Get the root component of the active design
    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    rootComp = design.rootComponent
    app.activeViewport.refresh()

    # Creates Progress Bar
    progressBar = ui.createProgressDialog()

    # Creates List of assembly components that contain joints
    assemblyOcc = [rootComp]
    for occ in findJointAssemblies(rootComp.occurrences):
        assemblyOcc.append(occ)


    # -Loops through Joints in Assemblies-

    # (First Assembled Group is Base Group)
    assembledComps = [[]]
    _assembledComps = [rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())]
    _assembledComps[0].component.name = "base_link"

    # Does Rigid Groups First
    if progressBar.wasCancelled:
        return True
    progressBar.show("Converting Robot File", "Step 1: Analyzing Joint Data...", 0, len(assemblyOcc) * 4, 0)
    progressBar.progressValue = 0

    for occs in assemblyOcc:
        occ = occs if occs == rootComp else occs.component
        for rg in occ.rigidGroups:
            if occs != rootComp:
                rg = rg.createForAssemblyContext(occs)
            # New Component per RigidGroup
            newComp = rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
            newComp.component.name = "unitycomp_" + str(len(assembledComps))
            newCompNames = []
            for o in range(rg.occurrences.count):
                occRG = rg.occurrences.item(o)
                for i in range(len(assembledComps)):
                    # If Comp Already in Link, Absorb Previous Linked Components into One
                    if occRG.fullPathName in assembledComps[i]:
                        for compName in assembledComps[i]:
                            newCompNames.append(compName)
                        assembledComps[i] = []
                        _assembledComps[i].deleteMe()
                        break
                # Else, Create Link for New Component
                else:
                    newCompNames.append(occRG.fullPathName)
            # Stores Linked info into Arrays
            assembledComps.append(newCompNames)
            _assembledComps.append(newComp)
        if progressBar.wasCancelled:
            return True
        progressBar.progressValue += 1

    # Does Rigid Joints Next
    for occs in assemblyOcc:
        occ = occs if occs == rootComp else occs.component
        for rigidJoint in occ.joints:
            # Joins Rigid Joint Components together
            if (rigidJoint.jointMotion.jointType == 0):
                if occs != rootComp:
                    rigidJoint = rigidJoint.createForAssemblyContext(occs)
                jointsOcc = [rigidJoint.occurrenceOne, rigidJoint.occurrenceTwo]
                # -Repeat of RigidGroup Code-
                # New Component per Rigid Joint
                newComp = rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
                newComp.component.name = "unitycomp_" + str(len(assembledComps))
                newCompNames = []
                for occRG in jointsOcc:
                    for i in range(len(assembledComps)):
                        # If Comp Already in Link, Absorb Previous Linked Components into One
                        if occRG.fullPathName in assembledComps[i]:
                            for compName in assembledComps[i]:
                                newCompNames.append(compName)
                            assembledComps[i] = []
                            _assembledComps[i].deleteMe()
                            break
                    # Else, Create Link for New Component
                    else:
                        newCompNames.append(occRG.fullPathName)
                # Stores Linked info into Arrays
                assembledComps.append(newCompNames)
                _assembledComps.append(newComp)
        if progressBar.wasCancelled:
            return True
        progressBar.progressValue += 1

    # Does Revolve Joints Last
    jointCount = 0
    for occs in assemblyOcc:
        occ = occs if occs == rootComp else occs.component
        for revJoint in occ.joints:
            # Recreate Joints with "Free" JointOrigins
            if (revJoint.jointMotion.jointType == 1 and not revJoint.name.startswith("unityjoint_")):
                if occs != rootComp:
                    revJoint = revJoint.createForAssemblyContext(occs)
                jointOrigins = []
                jointsOcc = [revJoint.occurrenceOne, revJoint.occurrenceTwo]
                if not jointsOcc[1]:
                    jointsOcc[1] = rootComp
                jointsComp = []
                # Sets Correct Origin Based on Occurrence not Component (Also only 1 origin for offset purposes)
                if revJoint.geometryOrOriginTwo.objectType == adsk.fusion.JointOrigin.classType():
                    joint = revJoint.geometryOrOriginTwo.geometry
                else:
                    joint = revJoint.geometryOrOriginTwo
                jointsOrigin = joint.origin
                try:
                    if joint.entityOne.objectType == adsk.fusion.ConstructionPoint.classType():
                        baseComp = joint.entityOne.component
                    elif joint.entityOne.objectType == adsk.fusion.SketchPoint.classType():
                        baseComp = rootComp
                    else:
                        baseComp = joint.entityOne.body.parentComponent
                except:
                    ui.messageBox("Whoops! It seems Joint: \"" + revJoint.name + "\" is connected to a currently not supported piece of Geometry! In a future update this may be fixed.")
                    joint.entityOne.body.parentComponent
                baseComp = rootComp.allOccurrencesByComponent(baseComp).item(0)
                if baseComp:
                    transform = baseComp.transform2
                    transform.invert()
                    transform.transformBy(jointsOcc[1].transform2)
                    jointsOrigin.transformBy(transform)
                for o in range(2):
                    # Creates Unlinked Components
                    for i in range(len(assembledComps)):
                        if jointsOcc[o] == rootComp:
                            continue
                        if jointsOcc[o].fullPathName in assembledComps[i]:
                            jointsComp.append(_assembledComps[i].component)
                            break
                    else:
                        # (Section for Base Components)
                        if o == 1:
                            baseLink = True
                            for controlJoints in jointsOcc[1].nativeObject.joints:
                                if jointsOcc[1] == controlJoints.occurrenceOne:
                                    baseLink = False
                            if jointsOcc[1] == rootComp or baseLink:
                                jointsComp.append(_assembledComps[0].component)
                                if jointsOcc[1] == rootComp:
                                    assembledComps[0].append(jointsOcc[o].name)
                                else:
                                    assembledComps[0].append(jointsOcc[o].fullPathName)
                        else:
                            jointsComp.append(rootComp.occurrences.addNewComponent(adsk.core.Matrix3D.create()))
                            jointsComp[o].component.name = "unitycomp_" + str(len(assembledComps))
                            assembledComps.append([jointsOcc[o].fullPathName])
                            _assembledComps.append(jointsComp[o])
                            jointsComp[o] = jointsComp[o].component
                    # Creates Point of Joint
                    pointInput = jointsComp[o].constructionPoints.createInput()
                    pointInput.setByPoint(jointsOrigin)
                    jointPoint = jointsComp[o].constructionPoints.add(pointInput)
                    # Creates Line of Axis
                    orig_vec = revJoint.jointMotion.rotationAxisVector
                    inf_line = adsk.core.InfiniteLine3D.create(jointsOrigin, orig_vec)
                    lineInput = jointsComp[o].constructionAxes.createInput()
                    lineInput.setByLine(inf_line)
                    jointLine = jointsComp[o].constructionAxes.add(lineInput)
                    # Creates Joint Origin
                    originInput = jointsComp[o].jointOrigins.createInput(adsk.fusion.JointGeometry.createByPoint(jointPoint))
                    originInput.zAxisEntity = jointLine
                    jointOrigins.append(jointsComp[o].jointOrigins.add(originInput))
                # Sets Joint Origin to be new Link
                #rootComp.joints.item(j).geometryOrOriginOne = jointOrigins[0]
                #rootComp.joints.item(j).geometryOrOriginTwo = jointOrigins[1]
                jointInput = rootComp.joints.createInput(jointOrigins[0], jointOrigins[1])
                jointInput.setAsRevoluteJointMotion(revJoint.jointMotion.rotationAxis)
                # Transfers Data
                jointInput.jointMotion.rotationLimits.isMaximumValueEnabled = revJoint.jointMotion.rotationLimits.isMaximumValueEnabled
                jointInput.jointMotion.rotationLimits.isMinimumValueEnabled = revJoint.jointMotion.rotationLimits.isMinimumValueEnabled
                jointInput.jointMotion.rotationLimits.isRestValueEnabled = revJoint.jointMotion.rotationLimits.isRestValueEnabled
                jointInput.jointMotion.rotationLimits.maximumValue = revJoint.jointMotion.rotationLimits.maximumValue
                jointInput.jointMotion.rotationLimits.minimumValue = revJoint.jointMotion.rotationLimits.minimumValue
                jointInput.jointMotion.rotationLimits.restValue = revJoint.jointMotion.rotationLimits.restValue
                # Adds New Rev Joint
                rootComp.joints.add(jointInput).name = "unityjoint_" + str(jointCount)
                jointCount += 1
        if progressBar.wasCancelled:
            return True
        progressBar.progressValue += 2
    app.activeViewport.refresh()

    # Remove Small Bodies
    progressBar.show("Converting Robot File", "Step 2: Removing Small Bodies...", 0, rootComp.occurrences.count - len(assembledComps), 0)
    progressBar.progressValue = 0
    removeSmallInAssembly(rootComp.occurrences.asList, progressBar, rootComp)

    # New Meshing Code
    progressBar.show("Converting Robot File", "Step 3: Combining Occurrences...", 0, len(assembledComps), 0)
    progressBar.progressValue = 0
    #combineAssembly(rootComp.occurrences.asList, assembledComps, _assembledComps, progressBar, rootComp)
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
                newOcc.moveToComponent(_assembledComps[i])
        progressBar.progressValue += 1
    while rootComp.occurrences.item(0).name != "base_link:1":
        rootComp.occurrences.item(0).moveToComponent(_assembledComps[0])
    progressBar.progressValue += 1

    # Previous Code
    '''
    # Big Loop of all Components to put into Linked _UnityComp_ Components
    traverseAssembly(rootComp.occurrences.asList, assembledComps, _assembledComps, progressBar, rootComp)
    app.activeViewport.refresh()
    if progressBar.wasCancelled:
        return True


    # Meshes and combines all bodies in Components
    progressBar.show("Converting Robot File", "Step 3: Creating Final Meshes...", 0, rootComp.occurrences.count * 2, 0)
    progressBar.progressValue = 0
    select = ui.activeSelections

    # Loops through Occurrences
    for o in range(rootComp.occurrences.count):
        occ = rootComp.occurrences.item(o)
        select.clear()

        # Creates Low Quality Meshes from Bodies
        txtCmds = ['Commands.Start ParaMeshTessellateCommand', 'NuCommands.CommitCmd']
        for bod in occ.component.bRepBodies:
            select.add(bod.createForAssemblyContext(rootComp.allOccurrences[o]))
        app.executeTextCommand(txtCmds[0])
        app.executeTextCommand(txtCmds[1])
        progressBar.progressValue += 1
        app.activeViewport.refresh()
        if progressBar.wasCancelled:
            return True

        # Reduces Mesh to Lower Quality
        txtCmds = ['Commands.Start ParaMeshReduceCommand', 'Commands.setDouble infoReduceProportion 10', 'NuCommands.CommitCmd']
        if o == 0:
            txtCmds = ['Commands.Start ParaMeshReduceCommand', 'Commands.setDouble infoReduceProportion 5', 'NuCommands.CommitCmd']
        for bod in occ.component.meshBodies:
            select.add(bod.createForAssemblyContext(rootComp.allOccurrences[o]))
            for cmd in txtCmds:
                app.executeTextCommand(cmd)
        progressBar.progressValue += 1
        app.activeViewport.refresh()
        if progressBar.wasCancelled:
            return True
    '''

    # Store Meshes
    ui.messageBox("Select Location to Store Folder of Robot Data", "Almost Finished!")

    folderDia = ui.createFolderDialog()
    folderDia.title = "Select Location to Store Folder of Robot Data"
    dlgResults = folderDia.showDialog()

    if dlgResults != 0:
        return

    exportPath = folderDia.folder + "/" + app.activeDocument.name

    if not os.path.exists(exportPath):
        os.makedirs(exportPath)

    progressBar.show("Converting Robot File", "Step 4: Creating Final Meshes...", 0, rootComp.occurrences.count, 0)
    progressBar.progressValue = 0

    # (Begins XML URDF File)
    root = minidom.Document()
    robot = root.createElement('robot')
    robot.setAttribute('name', app.activeDocument.name)
    root.appendChild(robot)

    for o in range(rootComp.occurrences.count):
        try:
            # STL
            occ = rootComp.occurrences.item(o)
            stlExport = design.exportManager.createSTLExportOptions(occ, exportPath + "/" + occ.name[:-2])
            stlExport.meshRefinement = 2
            stlExport.aspectRatio *= 10
            stlExport.maximumEdgeLength *= 10
            stlExport.normalDeviation *= 10
            stlExport.surfaceDeviation *= 10
            design.exportManager.execute(stlExport)
            # XML
            link = root.createElement('link')
            link.setAttribute('name', occ.name[:-2])
            robot.appendChild(link)
            vis = root.createElement('visual')
            link.appendChild(vis)
            geom = root.createElement('geometry')
            vis.appendChild(geom)
            mesh = root.createElement('mesh')
            mesh.setAttribute('filename', 'package://' + app.activeDocument.name + '/' + occ.name[:-2] + ".stl")
            geom.appendChild(mesh)
            coll = root.createElement('collision')
            link.appendChild(coll)
            coll.appendChild(geom.cloneNode(deep=True))
            # Progress
            progressBar.progressValue += 1
        except:
            # (Empty Occurrence)
            # XML
            link = root.createElement('link')
            link.setAttribute('name', occ.name[:-2])
            robot.appendChild(link)

    # Continues XML File
    #for motor in RobotConfig.configInfo["motors"]:

    for joint in rootComp.joints:
        if not joint.name.startswith('unityjoint_'):
            continue
        jnt = root.createElement('joint')
        jnt.setAttribute('name', joint.name)
        robot.appendChild(jnt)
        parent = root.createElement('parent')
        parent.setAttribute('link', joint.occurrenceTwo.name[:-2])
        jnt.appendChild(parent)
        child = root.createElement('child')
        child.setAttribute('link', joint.occurrenceOne.name[:-2])
        jnt.appendChild(child)
        axis = root.createElement('axis')
        rotAxis = joint.jointMotion.rotationAxisVector
        axis.setAttribute('xyz', str(rotAxis.x) + ' ' + str(rotAxis.y) + ' ' + str(rotAxis.z))
        jnt.appendChild(axis)
        if joint.jointMotion.rotationLimits.isMaximumValueEnabled:
            jnt.setAttribute('type', 'revolute')
            limit = root.createElement('limit')
            limit.setAttribute('upper', str(joint.jointMotion.rotationLimits.maximumValue))
            limit.setAttribute('lower', str(joint.jointMotion.rotationLimits.minimumValue))
            jnt.appendChild(limit)
        else:
            jnt.setAttribute('type', 'continuous')


    xml_string = root.toxml()

    f = open(exportPath + "/robotFile.urdf", "w")
    f.write(xml_string)
    f.close()

    app.activeDocument.save("")
    progressBar.hide()
    # Finally Exports Data
    #design.exportManager.

    ui.messageBox("Finished!")
    return False