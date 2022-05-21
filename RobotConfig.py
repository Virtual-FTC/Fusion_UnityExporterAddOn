# PHASE ONE SCRIPT - Asks user for input on Motors, Servos, and Sensors

import cmd
import configparser
from email.mime import application, base
from glob import glob
import json
from pickle import TRUE
import threading
import time
from turtle import update
import adsk.core, adsk.fusion, traceback


app = None
ui  = None
onStep = True

listOfJoints = []
configInfo = {"motors":[{"name":"frontLeft"}, {"name":"frontRight"}, {"name":"backLeft"}, {"name":"backRight"}],
 "servos":[], "sensors":[], "drive_train":{"standard":[], "mecanum":[], "omni":[], "encoder":[]}}
motorSelection = 0


# Global set of event handlers to keep them referenced for the duration of the command
_handlers = []

# Updates Table to current Values
def updateTable(tableInput, index):
    global motorSelection
    # Get the CommandInputs object associated with the parent command.
    cmdInputs = adsk.core.CommandInputs.cast(tableInput.commandInputs)

    # Removes Previous Entries
    while tableInput.rowCount > 0:
        tableInput.deleteRow(0)
    # Adds Updates Entries
    for i in range(len(configInfo["motors"])):
        if "name" in configInfo["motors"][i]:
            motorName = configInfo["motors"][i]["name"]
        else:
            motorName = "motor" + str(i)
        # Create three new command inputs.
        numberInput =  cmdInputs.addTextBoxCommandInput('motorsInput_number{}'.format(i), 'Text', str(i), 1, True)
        nameInput =  cmdInputs.addStringValueInput('motorsInput_name{}'.format(i), 'String', motorName)
        removeInput = cmdInputs.addBoolValueInput('motorsInput_remove{}'.format(i), 'Remove', False, '', True)

        # Add the inputs to the table.
        tableInput.addCommandInput(numberInput, i, 0)
        tableInput.addCommandInput(nameInput, i, 1)
        tableInput.addCommandInput(removeInput, i, 2)
    # Updates Selection
    tableInput.selectedRow = index
    motorSelection = index

    updateConfig(tableInput)

# Updates Config Values
def updateConfig(tableInput):
    motorConfigGroup = tableInput.parentCommand.commandInputs.itemById('motor_configuration')
    if motorSelection + 1 > tableInput.rowCount:
        motorConfigGroup.isVisible = False
    else:
        motorConfigGroup.isVisible = True
        motorConfigInputs = tableInput.parentCommand.commandInputs.itemById('motor_configuration').children
        # Joint Selection
        motorsInputSelect = motorConfigInputs.itemById('motor_joints')
        motorsInputSelect.clearSelection()
        if "joints" in configInfo["motors"][motorSelection]:
            for joint in configInfo["motors"][motorSelection]["joints"]:
                motorsInputSelect.addSelection(joint)
        # Reverse Joint Selection
        selectJoints(motorsInputSelect)
        # Gear Ratio
        motorsValueInput = motorConfigInputs.itemById('motor_ratio')
        motorsValueInput.value = 1
        if "ratio" in configInfo["motors"][motorSelection]:
            motorsValueInput.value = configInfo["motors"][motorSelection]["ratio"]
        # Motor Max RPM
        motorsValueInput = motorConfigInputs.itemById('motor_rpm')
        motorsValueInput.value = 340
        if "maxRPM" in configInfo["motors"][motorSelection]:
            motorsValueInput.value = configInfo["motors"][motorSelection]["maxRPM"]
        # Motor Max RPM
        motorsValueInput = motorConfigInputs.itemById('motor_encoders')
        motorsValueInput.value = 560
        if "ticksPerRev" in configInfo["motors"][motorSelection]:
            motorsValueInput.value = configInfo["motors"][motorSelection]["ticksPerRev"]

# Only Select Custom Graphics due to Joint Selection Issues
class MyPreSelectHandler(adsk.core.SelectionEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args: adsk.core.SelectionEventArgs):
        # Selection of the element under the mouse cursor.
        sel: adsk.core.Selection = args.selection
        ent = sel.entity

        if not ent:
            return False

        # Filtering by classType.
        if ent.classType() != adsk.fusion.CustomGraphicsPointSet.classType():
            # If not CustomGraphicsPointSet, disallow selection.
            args.isSelectable = False

# Adds Joint Selection Info into Config Object
def selectJoints(selectInput):
    motorsInputReverse = selectInput.parentCommandInput.children.itemById('motor_joints_reverse')
    motorsInputReverse.listItems.clear()
    if selectInput.selectionCount > 0:
        configInfo["motors"][motorSelection]["joints"] = []
        if "reverse" not in configInfo["motors"][motorSelection]:
            configInfo["motors"][motorSelection]["reverse"] = []
    elif "joints" in configInfo["motors"][motorSelection]:
        del configInfo["motors"][motorSelection]["joints"]
    # Adds Selections into corresponding joints array
    for i in range(selectInput.selectionCount):
        configInfo["motors"][motorSelection]["joints"].append(selectInput.selection(i).entity)
        thisJoint = None
        for joint in listOfJoints:
            if joint[0] == selectInput.selection(i).entity:
                thisJoint = joint[1]
                break
        motorsInputReverse.listItems.add("Joint " + str(i + 1) + ": " + thisJoint.name,
            selectInput.selection(i).entity in configInfo["motors"][motorSelection]["reverse"])
    reverseJoints(motorsInputReverse)

# Reverses joint info
def reverseJoints(dropDownInput):
    if "joints" not in configInfo["motors"][motorSelection]:
        configInfo["motors"][motorSelection]["joints"] = []
    configInfo["motors"][motorSelection]["reverse"] = []
    # Stores Info
    for i in range(dropDownInput.listItems.count):
        if dropDownInput.listItems.item(i).isSelected:
            configInfo["motors"][motorSelection]["reverse"].append(configInfo["motors"][motorSelection]["joints"][i])

# Tells joints to power
def testJoints(tabInput):
    # Hides Commands
    tabInput = tabInput.parentCommandInput.parentCommandInput
    if "joints" not in configInfo["motors"][motorSelection]:
        configInfo["motors"][motorSelection]["joints"] = []
    # Gets Joints and Reversals
    joints = []
    direction = []
    for jointLink in configInfo["motors"][motorSelection]["joints"]:
        for joint in listOfJoints:
            if joint[0] == jointLink:
                joints.append(joint[1])
                break
        if jointLink in configInfo["motors"][motorSelection]["reverse"]:
            direction.append(-1)
        else:
            direction.append(1)
    originalRot = [x.jointMotion.rotationValue for x in joints]
    # Updates to screen
    for i in range(15):
        # Updates Joints
        for j in range(len(joints)):
            joints[j].jointMotion.rotationValue += .25 * direction[j]
        if i % 3 == 0:
            adsk.doEvents()
        app.activeViewport.refresh()
        time.sleep(.01)
    # Reset Everything
    for j in range(len(joints)):
        joints[j].jointMotion.rotationValue = originalRot[j]
    updateConfig(tabInput.children.itemById('motors_table'))

# Saves values from selections
def driveTrainSave(selectInput):
    configInfo["drive_train"][selectInput.id[6:]] = []
    for i in range(selectInput.selectionCount):
        configInfo["drive_train"][selectInput.id[6:]].append(selectInput.selection(i).entity)

# Updates Values when changing tabs
def changeTabUpdate(inputs):
    # Reset Selections
    for input in inputs:
        if input.classType() == adsk.core.SelectionCommandInput.classType():
            input.clearSelection()
    # Motors Tab
    tabInput = inputs.itemById("tab_motors")
    if tabInput.isActive:
        updateConfig(tabInput.children.item(0))
        tabInput.children.item(1).children.item(0).hasFocus = True
    # Drive Train Tab
    tabInput = inputs.itemById("tab_drive")
    if tabInput.isActive:
        for i in range(4):
            selectId = tabInput.children.item(0).children.item(i).id[6:]
            for joint in configInfo["drive_train"][selectId]:
                tabInput.children.item(0).children.item(i).addSelection(joint)
        tabInput.children.item(0).children.item(0).hasFocus = True


# Event handler that reacts to any changes the user makes to any of the command inputs.
class MyCommandInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            global onStep
            if not onStep:
                return
            eventArgs = adsk.core.InputChangedEventArgs.cast(args)
            inputs = eventArgs.inputs
            cmdInput = eventArgs.input
            # SWITCH TABS
            if cmdInput.id.startswith("APITabBar"):
                changeTabUpdate(inputs)
            # MOTOR TAB
            # Motor Table Properties
            elif cmdInput.id.startswith("motors"):
                tableInput = inputs.itemById('motors_table')
                if cmdInput.id == "motors_move_up":
                    currentRow = tableInput.selectedRow
                    if currentRow > 0:
                        configInfo["motors"][currentRow], configInfo["motors"][currentRow - 1] = configInfo["motors"][currentRow - 1], configInfo["motors"][currentRow]
                        updateTable(tableInput, currentRow - 1)
                elif cmdInput.id == "motors_move_down":
                    currentRow = tableInput.selectedRow
                    if currentRow + 1 < tableInput.rowCount:
                        configInfo["motors"][currentRow], configInfo["motors"][currentRow + 1] = configInfo["motors"][currentRow + 1], configInfo["motors"][currentRow]
                        updateTable(tableInput, currentRow + 1)
                elif cmdInput.id == 'motors_add':
                    if tableInput.rowCount < 8:
                        configInfo["motors"].append({})
                        updateTable(tableInput, tableInput.rowCount)
                elif cmdInput.id.startswith("motorsInput_name"):
                    currentRow = int(cmdInput.id[16:])
                    if cmdInput.value != "motor" + str(currentRow):
                        configInfo["motors"][currentRow]["name"] = cmdInput.value
                    global motorSelection
                    motorSelection = currentRow
                    updateConfig(tableInput)
                elif cmdInput.id.startswith('motorsInput_remove'):
                    results = ui.messageBox("Are you sure you wish to delete this motor?", '', 3)
                    if results == 2:
                        currentRow = int(cmdInput.id[18:])
                        configInfo["motors"].pop(currentRow)
                        updateTable(tableInput, currentRow)
            # Motor Info Properties
            elif cmdInput.id.startswith("motor"):
                if cmdInput.id == 'motor_joints':
                    selectJoints(cmdInput)
                elif cmdInput.id == 'motor_joints_reverse':
                    reverseJoints(cmdInput)
                elif cmdInput.id == 'motor_power':
                    testJoints(cmdInput)
                elif cmdInput.id == 'motor_ratio':
                    configInfo["motors"][motorSelection]["ratio"] = cmdInput.value
                elif cmdInput.id == 'motor_rpm':
                    configInfo["motors"][motorSelection]["maxRPM"] = cmdInput.value
                elif cmdInput.id == 'motor_encoders':
                    configInfo["motors"][motorSelection]["ticksPerRev"] = cmdInput.value
            # DRIVE TRAIN TAB
            # Save Drive Train Joints
            elif cmdInput.id.startswith("drive"):
                driveTrainSave(cmdInput)
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()


# Event handler that reacts to when the command is destroyed. This terminates the script.            
class MyCommandDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # When the command is done, terminate the script
            # This will release all globals which will remove all event handlers
            global onStep
            if not onStep:
                return
            #cmdDef = ui.commandDefinitions.itemById('cmdInputsConfig')
            #cmdDef.execute()
            
            adsk.terminate()
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()


# Event handler for the execute event.
class MyExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Code to react to the event.
            global onStep
            if not onStep:
                return
            onStep = False

            design = adsk.fusion.Design.cast(app.activeProduct)
            rootComp = design.rootComponent
            # Check to see if a custom graphics groups already exists and delete it.
            while rootComp.customGraphicsGroups.count > 0:
                rootComp.customGraphicsGroups.item(0).deleteMe()
            app.activeViewport.refresh()

            # Makes sure configinfo is filled (This confusing system will be fixed soon)
            for i in range(len(configInfo["motors"])):
                if "joints" not in configInfo["motors"][i]:
                    configInfo["motors"][i]["joints"] = []
                if "reverse" not in configInfo["motors"][i]:
                    configInfo["motors"][i]["reverse"] = []
                if "ratio" not in configInfo["motors"][i]:
                    configInfo["motors"][i]["ratio"] = 1
                if "maxRPM" not in configInfo["motors"][i]:
                    configInfo["motors"][i]["maxRPM"] = 340
                if "ticksPerRev" not in configInfo["motors"][i]:
                    configInfo["motors"][i]["ticksPerRev"] = 560

            # Move on to next phase!
            myCustomEvent = 'Phase2-MeshThread'
            app.fireCustomEvent(myCustomEvent, '') 
        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()

# Event handler that reacts when the command definitio is executed which
# results in the command being created and this event being fired.
class MyCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            # Get the command that was created.
            cmd = adsk.core.Command.cast(args.command)

            onPreSelect = MyPreSelectHandler()
            cmd.preSelect.add(onPreSelect)
            _handlers.append(onPreSelect)

            # Connect to the command destroyed event.
            onDestroy = MyCommandDestroyHandler()
            cmd.destroy.add(onDestroy)
            _handlers.append(onDestroy)

            # Connect to command completed event.
            onExecute = MyExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)

            # Connect to the input changed event.           
            onInputChanged = MyCommandInputChangedHandler()
            cmd.inputChanged.add(onInputChanged)
            _handlers.append(onInputChanged)    

            # Get the CommandInputs collection associated with the command.
            inputs = cmd.commandInputs

            # Tab for Motors
            tabMotors = inputs.addTabCommandInput('tab_motors', 'Motors')
            tabMotorsInputs = tabMotors.children

            # Table of Motors
            motorsInput = tabMotorsInputs.addTableCommandInput('motors_table', 'Motors', 3, '1:6:3')
            motorsInput.minimumVisibleRows = 4
            motorsInput.maximumVisibleRows = 8

            # Move inputs up the table            
            upButtonInput = tabMotorsInputs.addBoolValueInput('motors_move_up', '▲', False, '', True)
            motorsInput.addToolbarCommandInput(upButtonInput)

            # Move inputs down the table            
            downButtonInput = tabMotorsInputs.addBoolValueInput('motors_move_down', '▼', False, '', True)
            motorsInput.addToolbarCommandInput(downButtonInput)

            # Add inputs into the table            
            addButtonInput = tabMotorsInputs.addBoolValueInput('motors_add', 'Add Motor', False, '', True)
            motorsInput.addToolbarCommandInput(addButtonInput)

            # Create group for Motor Config
            motorConfigGroup = tabMotorsInputs.addGroupCommandInput("motor_configuration", "Motor Configuration")
            motorConfigInputs = motorConfigGroup.children

            # Select Joints
            motorsInputSelect = motorConfigInputs.addSelectionInput('motor_joints', 'Joints', 'Select Joints this Motor affects')
            motorsInputSelect.setSelectionLimits(0)

            # Reverse Joints Option
            motorsInputReverse = motorConfigInputs.addDropDownCommandInput('motor_joints_reverse', 'Reverse Joints', adsk.core.DropDownStyles.CheckBoxDropDownStyle)
            motorsInputReverse.listItems.add('Joint 1', False)
            motorsInputReverse.listItems.add('Joint 2', False)

            # Slider to Visualize Movement (Too much lag and unresponsive commands)
            #motorsInputPower = motorConfigInputs.addFloatSliderListCommandInput('motor_power', 'Test Movement', '', [-1, -.5, 0, .5, 1])
            #motorsInputPower.valueOne = 0
            #motorsInputPower.setText('-1', '1 ')

            # Button to Visualize Movement
            motorConfigInputs.addBoolValueInput('motor_power', ' [Test Direction]', False, 'resources/Power', False)

            # Values for Motors
            motorConfigInputs.addFloatSpinnerCommandInput('motor_ratio', 'Gear Ratio', '', .01, 10000, .25, 1)
            motorConfigInputs.addIntegerSpinnerCommandInput('motor_rpm', 'Max RPM', 0, 10000, 10, 340)
            motorConfigInputs.addFloatSpinnerCommandInput('motor_encoders', 'Encoder Ticks', '', 0, 10000, 10, 560)

            # Updates Motor Table
            updateTable(motorsInput, 0)

            # Tab for Servos
            #tabServos = inputs.addTabCommandInput('tab_servos', 'Servos')
            #tabServosInputs = tabServos.children

            # Tab for Sensors
            #tabSensors = inputs.addTabCommandInput('tab_sensors', 'Sensors')
            #tabSensorsInputs = tabSensors.children

            # Tab for Drive Train
            tabDrive = inputs.addTabCommandInput('tab_drive', 'Drive Train')
            tabDriveInputs = tabDrive.children

            # Create group for Motor Config
            driveConfigGroup = tabDriveInputs.addGroupCommandInput("drive_configuration", "Select Corresponding Joints")
            driveConfigInputs = driveConfigGroup.children

            # Select Joints for Standard
            standardInputSelect = driveConfigInputs.addSelectionInput('drive_standard', 'Standard Wheels', 'Select Joints that control Standard Wheels')
            standardInputSelect.setSelectionLimits(0)

            # Select Joints for Mecanum
            mecanumInputSelect = driveConfigInputs.addSelectionInput('drive_mecanum', 'Mecanum Wheels', 'Select Joints that control Mecanum Wheels')
            mecanumInputSelect.setSelectionLimits(0)

            # Select Joints for Omni
            omniInputSelect = driveConfigInputs.addSelectionInput('drive_omni', 'Omni Wheels', 'Select Joints that control Omni Wheels')
            omniInputSelect.setSelectionLimits(0)

            # Select Joints for Encoders
            encoderInputSelect = driveConfigInputs.addSelectionInput('drive_encoder', 'Encoder Wheels', 'Select Joints that link Encoder Wheels')
            encoderInputSelect.setSelectionLimits(0)

        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()


def runConfig():
    global app, ui
    app = adsk.core.Application.get()
    ui = app.userInterface

    design = adsk.fusion.Design.cast(app.activeProduct)
    rootComp = design.rootComponent

    # Check to see if a custom graphics groups already exists and delete it.
    while rootComp.customGraphicsGroups.count > 0:
        rootComp.customGraphicsGroups.item(0).deleteMe()
    app.activeViewport.refresh()

    # Create a graphics group on the root component.
    graphics = rootComp.customGraphicsGroups.add()

    # Loops through all joints and places point for selection purposes
    for revJoint in rootComp.allJoints:
        if revJoint.jointMotion.jointType != 1:
            continue
        # <<Taken from MeshExporter>>
        jointsOcc = [None, revJoint.occurrenceTwo]
        if not jointsOcc[1]:
            jointsOcc[1] = rootComp
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
            ui.messageBox("Whoops! It seems Joint: \"" + joint.name + "\" is connected to a currently not supported piece of Geometry! In a future update this may be fixed.")
            joint.entityOne.body.parentComponent
        baseComp = rootComp.allOccurrencesByComponent(baseComp).item(0)
        if baseComp:
            transform = baseComp.transform2
            transform.invert()
            transform.transformBy(jointsOcc[1].transform2)
            jointsOrigin.transformBy(transform)
        # Adds Point Graphic
        coord = adsk.fusion.CustomGraphicsCoordinates.create(jointsOrigin.asArray())
        point = graphics.addPointSet(coord, [0], adsk.fusion.CustomGraphicsPointTypes.UserDefinedCustomGraphicsPointType,
            'resources/SelectJoint.png')
        # Add to Array
        listOfJoints.append([point, revJoint])

    app.activeViewport.refresh()

    # Get the existing command definition or create it if it doesn't already exist.
    cmdDef = ui.commandDefinitions.itemById('cmdInputsConfig')
    if not cmdDef:
        cmdDef = ui.commandDefinitions.addButtonDefinition('cmdInputsConfig', 'Configure Robot', 'Input config info to save to Unity.')

    # Connect to the command created event.
    onCommandCreated = MyCommandCreatedHandler()
    cmdDef.commandCreated.add(onCommandCreated)
    _handlers.append(onCommandCreated)

    # Execute the command definition.
    cmdDef.execute()

    # Prevent this module from being terminated when the script returns, because we are waiting for event handlers to fire.
    adsk.autoTerminate(False)