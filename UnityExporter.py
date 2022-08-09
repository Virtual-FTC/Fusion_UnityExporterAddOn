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
        ui.messageBox("1. Select the Wheel Components on the Robot", "Configuration Steps")

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
            ui.messageBox("2. Select Location to Store Folder of Robot Data", "Configuration Steps")

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
def createJntXML(revJoint, parentNum, childNum, jointCount):
    root = minidom.Document()
    jntXML = root.createElement('joint')
    jntXML.setAttribute('name', "unityjoint_" + str(jointCount))
    parent = root.createElement('parent')
    parent.setAttribute('link', "unitycomp_" + str(parentNum))
    jntXML.appendChild(parent)
    child = root.createElement('child')
    child.setAttribute('link', "unitycomp_" + str(childNum))
    jntXML.appendChild(child)
    axis = root.createElement('axis')
    rotAxis = revJoint.jointMotion.rotationAxisVector
    rotAxis.transformBy(MeshExporter.newTransform)
    axis.setAttribute('xyz', str(rotAxis.x) + ' ' + str(rotAxis.y) + ' ' + str(rotAxis.z))
    jntXML.appendChild(axis)
    # Finds Origin of Joint
    jointsOrigin = MeshExporter.jointOriginWorldSpace(revJoint)
    jointsOrigin.transformBy(MeshExporter.newTransform)
    origin = root.createElement('origin')
    origin.setAttribute('xyz', str(jointsOrigin.x) + " " + str(jointsOrigin.y) + " " + str(jointsOrigin.z))
    jntXML.appendChild(origin)
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

    attributes = root.createElement('attributes')
    point = rootComp.boundingBox.maxPoint
    rootComp.transformOccurrences
    boxStr = str(point.x) + " " + str(point.y) + " " + str(point.z)
    point = rootComp.boundingBox.minPoint
    boxStr += ", " + str(point.x) + " " + str(point.y) + " " + str(point.z)
    attributes.setAttribute('boundingBox', boxStr)
    robot.appendChild(attributes)

    # Adds Links just for mass reading purposes
    for occ in rootComp.occurrences[0].childOccurrences:
        lnkXML = root.createElement('link')
        lnkXML.setAttribute('name', occ.name[:-2])
        robot.appendChild(lnkXML)
        if occ.isLightBulbOn:
            # Sets Mass Info
            massXML = root.createElement('mass')
            massXML.setAttribute('value', str(occ.physicalProperties.mass))
            lnkXML.appendChild(massXML)
        else:
            # Wheel Joint
            wheelXML = root.createElement('wheel')
            wheelXML.setAttribute('type', '')
            wheelXML.setAttribute('offset', '0')
            lnkXML.appendChild(wheelXML)

    # Adds the Previously calculated JntXMLS
    for jntXML in jntXMLS:
        # Checks for dissolved groups
        dissolved = True
        for occ in rootComp.occurrences[0].childOccurrences:
            if occ.name[:-2] == jntXML.firstChild.getAttribute("link"):
                dissolved = False
                break
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
        #if app.activeDocument.isModified and started:
        #    dataFile = app.activeDocument.dataFile
        #    app.activeDocument.close(False)
        #    app.documents.open(dataFile)
        ui.messageBox("tempdisable")
    except:
        ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))