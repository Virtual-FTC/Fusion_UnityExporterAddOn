#Author- VRS Team
#Description- Fusion Exporter to import files into Unity for the VRS

import os
from xml.dom import minidom
import adsk.core, adsk.fusion, adsk.cam, traceback

from . import MeshExporter

app = None
ui = adsk.core.UserInterface.cast(None)

started = False
exportPath = ""

_handlers = []

# Starting Function
def run(context):
    global app, ui, started
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        
        # Opening Statement
        statement = '''Welcome to the Unity Exporter for the Virtual Robot Simulator!

If you experience any issues, feel free to reach out!'''

        results = ui.messageBox(statement, "UNITY EXPORTER", 1)
        if results == 1:
            ui.messageBox("Cancelled Task")
            adsk.terminate()
            return

        # Opening Statement
        statement = '''Before hitting "OK", be sure that your robot includes all needed joints!

Also make sure to support 4 Bar Parallel Lifts with Joints on Both Sides!'''

        results = ui.messageBox(statement, "IMPORTANT INFO", 1)
        if results == 1:
            ui.messageBox("Cancelled Task")
            adsk.terminate()
            return

        # Creates Progress Bar
        progressBar = ui.createProgressDialog()

        #Saves File if not saved before starting
        if app.activeDocument.isModified:
            progressBar.show("Converting Robot File", "Saving File...", 0, 1, 0)
            progressBar.progressValue = 1
            app.activeViewport.refresh()
            adsk.doEvents()
            app.activeDocument.save("")

        # Modifies Current Document Settings
        started = True
        progressBar.show("Converting Robot File", "Modifying File...", 0, 1, 0)
        progressBar.progressValue = 1
        app.activeViewport.refresh()
        adsk.doEvents()
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = 0
        design.fusionUnitsManager.distanceDisplayUnits = 0

        progressBar.hide()

        # First: Select Wheels (This is created here to save global variables)
        ui.messageBox("[1/2] In the Next Step:\n   Select the Wheel Components on the Robot", "Configuration Steps")

        # Get the existing command definition or create it if it doesn't already exist.
        cmdDef = ui.commandDefinitions.itemById('cmdWheelsConfig')
        if not cmdDef:
            cmdDef = ui.commandDefinitions.addButtonDefinition('cmdWheelsConfig', 'Configure Wheels', 'Select Wheels to save into Unity.')

        # Connect to the command created event.
        onCommandCreated = MyCommandCreatedHandler()
        cmdDef.commandCreated.add(onCommandCreated)
        _handlers.append(onCommandCreated)

        # Execute the command definition.
        cmdDef.execute()

        # Prevent this module from being terminated when the script returns, because we are waiting for event handlers to fire.
        adsk.autoTerminate(False)
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
        adsk.terminate()



# Event handler that reacts when the command definition is executed which
# results in the command being created and this event being fired.
class MyCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Get the command that was created.
            cmd = adsk.core.Command.cast(args.command)

            # Connect to the command destroyed event.
            onDestroy = MyCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            _handlers.append(onDestroy)

            # Connect to command completed event.
            onExecute = MyExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)

            # Get the CommandInputs collection associated with the command.
            inputs = cmd.commandInputs

            # Add Wheel Selector
            selector = inputs.addSelectionInput('wheels', 'Wheel Components', 'Select Components that contain a Wheel')
            selector.setSelectionLimits(0)
            selector.addSelectionFilter("Occurrences")
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()

# Event handler that reacts to when the command is destroyed. This terminates the script.            
class MyCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        ui.messageBox("Cancelled Task")
        adsk.terminate()

# Event handler for the execute event.
class MyExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Removes Menu
            cmd = adsk.core.Command.cast(args.command)
            cmd.destroy.remove(_handlers[1])
            cmd.execute.remove(_handlers[2])

            # Bug: CmdDef can't be deleted
            cmd.parentCommandDefinition.deleteMe()

            # Returns Data
            selector = adsk.core.Command.cast(args.command).commandInputs.item(0)

            wheelOccs = [selector.selection(i).entity.fullPathName for i in range(selector.selectionCount)]

            adsk.terminate()

            selector.isVisible = False
            selector.isEnabled = False
            selector.deleteMe()

            # Next Step: Ask Location to store
            ui.messageBox("[2/2] In the Next Step:\n   Select the Location to Store the Folder of the Robot Data", "Configuration Steps")

            folderDia = ui.createFolderDialog()
            folderDia.title = "Select Location to Store Folder of Robot Data"
            dlgResults = folderDia.showDialog()

            if dlgResults != 0:
                ui.messageBox("Cancelled Task")
                adsk.terminate()
                return

            global exportPath
            exportPath = folderDia.folder + "/" + app.activeDocument.name

            # Start Meshing Function
            jntXMLS = MeshExporter.runMesh(wheelOccs)
            if not jntXMLS:
                ui.messageBox("Cancelled Task")
                adsk.terminate()
                return

            # Does Final Step
            finalExport(jntXMLS)
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()


# Creates JntXML mid MeshExporter as combining components can break joints
def createJntXML(jointObj, parentNum, childNum, jointCount):
    root = minidom.Document()
    # Creates Basic Joint Setup
    jntXML = root.createElement('joint')
    jntXML.setAttribute('name', "unityjoint_" + str(jointCount))
    parent = root.createElement('parent')
    parent.setAttribute('link', "unitycomp_" + str(parentNum))
    jntXML.appendChild(parent)
    child = root.createElement('child')
    child.setAttribute('link', "unitycomp_" + str(childNum))
    jntXML.appendChild(child)
    # Revolute or Prismatic Joint
    if jointObj.jointMotion.jointType == 1:
        jntXML.setAttribute('type', 'revolute')
        jntAxis = jointObj.jointMotion.rotationAxisVector
        jntLimit = jointObj.jointMotion.rotationLimits
    elif jointObj.jointMotion.jointType == 2:
        jntXML.setAttribute('type', 'prismatic')
        jntAxis = jointObj.jointMotion.slideDirectionVector
        jntLimit = jointObj.jointMotion.slideLimits
    # Sets Axis of Travel for Joints
    axis = root.createElement('axis')
    jntAxis.transformBy(MeshExporter.newTransform)
    if abs(jntAxis.x) < .01: jntAxis.x = 0
    if abs(jntAxis.y) < .01: jntAxis.y = 0
    if abs(jntAxis.z) < .01: jntAxis.z = 0
    axis.setAttribute('xyz', str(jntAxis.x) + ' ' + str(jntAxis.y) + ' ' + str(jntAxis.z))
    jntXML.appendChild(axis)
    # Finds Origin of Joint
    jointsOrigin = MeshExporter.jointOriginWorldSpace(jointObj)
    jointsOrigin.transformBy(MeshExporter.newTransform)
    origin = root.createElement('origin')
    origin.setAttribute('xyz', str(jointsOrigin.x) + " " + str(jointsOrigin.y) + " " + str(jointsOrigin.z))
    jntXML.appendChild(origin)
    # Sets Limits if Found
    limit = root.createElement('limit')
    lowerLimit = ""
    if jntLimit.isMinimumValueEnabled:
        lowerLimit = str(jntLimit.minimumValue)
    limit.setAttribute('lower', lowerLimit)
    upperLimit = ""
    if jntLimit.isMaximumValueEnabled:
        upperLimit = str(jntLimit.maximumValue)
    limit.setAttribute('upper', upperLimit)
    jntXML.appendChild(limit)

    # --ADD MOTION LINKS? (Not exposed to API)--

    return jntXML


# Export Function for URDF and STL Files
def finalExport(jntXMLS):
    global app, ui

    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    rootComp = design.rootComponent

    progressBar = ui.createProgressDialog()
    progressBar.show("Converting Robot File", "Step 4: Creating URDF File...", 0, 1, 0)
    progressBar.progressValue = 1
    app.activeViewport.refresh()
    adsk.doEvents()

    # Orients Components
    rootComp.occurrences[0].transform = MeshExporter.newTransform

    # Creates XML URDF File
    root = minidom.Document()
    robot = root.createElement('robot')
    robot.setAttribute('name', app.activeDocument.name)
    root.appendChild(robot)

    # Adds Links just for mass reading purposes
    for occ in rootComp.occurrences[0].childOccurrences:
        if occ.isLightBulbOn:
            lnkXML = root.createElement('link')
            lnkXML.setAttribute('name', occ.name[:-2])
            robot.appendChild(lnkXML)
            # Sets Mass Info
            massXML = root.createElement('mass')
            massXML.setAttribute('value', str(occ.physicalProperties.mass))
            lnkXML.appendChild(massXML)

    # Adds the Previously calculated JntXMLS
    for jntXML in jntXMLS:
        dissolved = True
        for occ in rootComp.occurrences[0].childOccurrences:
            # Checks if comp still exists
            if occ.name[:-2] == jntXML.firstChild.getAttribute("link"): # parent
                dissolved = False
            # Check if is a wheel
            if occ.name[:-2] == jntXML.childNodes[1].getAttribute("link"): # child
                if not occ.isLightBulbOn:
                    wheelXML = root.createElement('wheel')
                    wheelXML.setAttribute('type', '')
                    '''
                    # Doesn't work due to axels being apart of wheel object so better to set in importer
                    
                    # Gets offset and center properties
                    axis = adsk.core.Vector3D.create(0, 0, 0)
                    axis.setWithArray([float(i) for i in jntXML.childNodes[2].getAttribute("xyz").split(' ')])
                    origin = adsk.core.Vector3D.create(0, 0, 0)
                    origin.setWithArray([float(i) for i in jntXML.childNodes[3].getAttribute("xyz").split(' ')])
                    yAxis = adsk.core.Vector3D.create(0, 1, 0)
                    newTransform = adsk.core.Matrix3D.create()
                    newTransform.setToAlignCoordinateSystems(origin.asPoint(), axis, yAxis, axis.crossProduct(yAxis),
                        adsk.core.Point3D.create(0, 0, 0), adsk.core.Vector3D.create(1, 0, 0), yAxis, adsk.core.Vector3D.create(0, 0, 1))
                    combinedTransform = MeshExporter.newTransform.copy()
                    combinedTransform.transformBy(newTransform)
                    occ.transform2 = combinedTransform
                    wheelXML.setAttribute('offset', str(occ.boundingBox.maxPoint.x))
                    '''
                    wheelXML.setAttribute('offset', "0")
                    jntXML.appendChild(wheelXML)
        if dissolved:
            jntXML.firstChild.setAttribute('link', 'unitycomp_0')
        robot.appendChild(jntXML)

    # Store Meshes
    if not os.path.exists(exportPath):
        os.makedirs(exportPath)

    xml_string = root.toxml()

    f = open(exportPath + "/robotfile.urdf", "w")
    f.write(xml_string)
    f.close()

    progressBar.show("Converting Robot File", "Step 5: Creating Final Meshes...", 0, rootComp.occurrences[0].childOccurrences.count, 0)
    progressBar.progressValue = 0

    for occ in rootComp.occurrences[0].childOccurrences:
        if occ.isLightBulbOn:
            try:
                # STL
                stlExport = design.exportManager.createSTLExportOptions(occ, exportPath + "/" + occ.name[:-2])
                stlExport.meshRefinement = 2
                stlExport.aspectRatio *= 10
                stlExport.maximumEdgeLength *= 10
                stlExport.normalDeviation *= 10
                stlExport.surfaceDeviation *= 10
                design.exportManager.execute(stlExport)
                # Progress
                if progressBar.wasCancelled:
                    ui.messageBox("Cancelled Task")
                    adsk.terminate()
                    return
            except:
                pass
        progressBar.progressValue += 1

    progressBar.hide()

    ui.messageBox('Check the folder "' + exportPath + '" for your finalized robot!', "Finished!")
    adsk.terminate()

# Clean up CAD File
def stop(context):
    try:
        if app.activeDocument.isModified and started:
            dataFile = app.activeDocument.dataFile
            app.activeDocument.close(False)
            app.documents.open(dataFile)
        #ui.messageBox("tempdisable")
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))