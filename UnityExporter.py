#Author- VRS Team
#Description- Fusion Exporter to import files into Unity for the VRS

import os
from xml.dom import minidom
import adsk.core, adsk.fusion, adsk.cam, traceback

from . import MeshExporter

app = None
ui = adsk.core.UserInterface.cast(None)

_handlers = []

docName = ""

# Starting Function
def run(context):
    global app, ui
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
        statement = '''Before hitting "OK", be sure that your robot has all included joints!'''

        results = ui.messageBox(statement, "IMPORTANT INFO", 1)
        if results == 1:
            ui.messageBox("Cancelled Task")
            adsk.terminate()
            return

        # Creates Progress Bar
        progressBar = ui.createProgressDialog()
        progressBar.show("Converting Robot File", "Cloning Last Saved File...", 0, 1, 0)
        progressBar.progressValue = 1

        # Delete any previous "Unity Export" Files
        for i in range(app.activeDocument.dataFile.parentFolder.dataFiles.count):
            if app.activeDocument.dataFile.parentFolder.dataFiles.item(i).name.startswith("Unity Export"):
                app.activeDocument.dataFile.parentFolder.dataFiles.item(i).deleteMe()
                break

        #Clone Current Document (Todo: Remove cloning *safely*)
        global docName
        docName = app.activeDocument.name
        data_orig = app.activeDocument.dataFile.copy(app.activeDocument.dataFile.parentFolder)
        data_orig.name = "Unity Export"
        app.documents.open(data_orig)

        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        design.designType = 0
        design.fusionUnitsManager.distanceDisplayUnits = 0

        progressBar.hide()

        # Meshing Function
        cancelled = MeshExporter.runMesh()
        if cancelled:
            ui.messageBox("Cancelled Task")
            adsk.terminate()
            return

        # Next step: Select Wheels (This is created here to save global variables)
        ui.messageBox("Select the Wheel Components on the Robot", "Almost Finished!")

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

            wheelOcc = [selector.selection(i).entity.fullPathName.split('+')[0] for i in range(selector.selectionCount)]

            selector.isVisible = False
            selector.isEnabled = False
            selector.deleteMe()

            finalExport(wheelOcc)
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()



# Export Function for URDF and STL Files
def finalExport(wheelOccNames = []):
    global app, ui, docName

    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    rootComp = design.rootComponent

    progressBar = ui.createProgressDialog()
    progressBar.show("Converting Robot File", "Step 4: Creating URDF File...", 0, 1, 0)
    progressBar.progressValue = 1
    app.activeViewport.refresh()
    adsk.doEvents()

    # Hides Wheel Occurrences
    for name in wheelOccNames:
        rootComp.occurrences.itemByName(name).isLightBulbOn = False

    # Creates XML URDF File
    root = minidom.Document()
    robot = root.createElement('robot')
    robot.setAttribute('name', docName)
    root.appendChild(robot)

    attributes = root.createElement('attributes')
    point = rootComp.boundingBox.maxPoint
    boxStr = str(point.x) + " " + str(point.y) + " " + str(point.z)
    point = rootComp.boundingBox.minPoint
    boxStr += ", " + str(point.x) + " " + str(point.y) + " " + str(point.z)
    attributes.setAttribute('boundingBox', boxStr)
    robot.appendChild(attributes)

    # Adds Links just for mass reading purposes
    for occ in rootComp.occurrences:
        lnkXML = root.createElement('link')
        lnkXML.setAttribute('name', occ.name[:-2])
        robot.appendChild(lnkXML)
        massXML = root.createElement('mass')
        massXML.setAttribute('value', str(occ.physicalProperties.mass))
        lnkXML.appendChild(massXML)

    # Adds Joints and their corresponding info
    for revJoint in rootComp.joints:
        if not revJoint.name.startswith('unityjoint_'):
            continue
        jntXML = root.createElement('joint')
        jntXML.setAttribute('name', revJoint.name)
        robot.appendChild(jntXML)
        parent = root.createElement('parent')
        parent.setAttribute('link', revJoint.occurrenceTwo.name[:-2])
        jntXML.appendChild(parent)
        child = root.createElement('child')
        child.setAttribute('link', revJoint.occurrenceOne.name[:-2])
        jntXML.appendChild(child)
        axis = root.createElement('axis')
        rotAxis = revJoint.jointMotion.rotationAxisVector
        axis.setAttribute('xyz', str(rotAxis.x) + ' ' + str(rotAxis.y) + ' ' + str(rotAxis.z))
        jntXML.appendChild(axis)
        # Finds Origin of Joint
        jointsOrigin = MeshExporter.jointOriginWorldSpace(revJoint, rootComp)
        origin = root.createElement('origin')
        origin.setAttribute('xyz', str(jointsOrigin.x) + " " + str(jointsOrigin.y) + " " + str(jointsOrigin.z))
        jntXML.appendChild(origin)
        # Checks if a wheel joint
        if not revJoint.occurrenceOne.isLightBulbOn:
            wheelXML = root.createElement('wheel')
            wheelXML.setAttribute('type', '')
            wheelXML.setAttribute('offset', '0')
            jntXML.appendChild(wheelXML)
        # Revolute (Limited) or Continuous
        if revJoint.jointMotion.rotationLimits.isMaximumValueEnabled:
            jntXML.setAttribute('type', 'revolute')
            limit = root.createElement('limit')
            limit.setAttribute('upper', str(revJoint.jointMotion.rotationLimits.maximumValue))
            limit.setAttribute('lower', str(revJoint.jointMotion.rotationLimits.minimumValue))
            jntXML.appendChild(limit)
        else:
            jntXML.setAttribute('type', 'continuous')

        # --ADD SLIDER JOINTS AND MOTION LINKS--

    # Store Meshes
    ui.messageBox("Select Location to Store Folder of Robot Data", "Almost Finished!")

    folderDia = ui.createFolderDialog()
    folderDia.title = "Select Location to Store Folder of Robot Data"
    dlgResults = folderDia.showDialog()

    if dlgResults != 0:
        ui.messageBox("Cancelled Task")
        adsk.terminate()
        return

    exportPath = folderDia.folder + "/" + docName

    if not os.path.exists(exportPath):
        os.makedirs(exportPath)

    xml_string = root.toxml()

    f = open(exportPath + "/robotfile.urdf", "w")
    f.write(xml_string)
    f.close()

    progressBar.show("Converting Robot File", "Step 5: Creating Final Meshes...", 0, rootComp.occurrences.count, 0)
    progressBar.progressValue = 0

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
            # Progress
            progressBar.progressValue += 1
        except:
            pass

    app.activeDocument.save("")
    progressBar.hide()

    ui.messageBox('Check the folder "' + exportPath + '" for your finalized robot!', "Finished!")
    adsk.terminate()