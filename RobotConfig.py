# PHASE ONE SCRIPT - Asks user for input on Motors, Servos, and Sensors

import cmd
import configparser
from email.mime import application, base
from glob import glob
from pickle import TRUE
from turtle import update
import adsk.core, adsk.fusion, traceback


app = None
ui  = None
onStep = True

configInfo = {"motors":[{"name":"frontLeft"}, {"name":"frontRight"}, {"name":"backLeft"}, {"name":"backRight"}],
 "servos":[], "sensors":[], "drive_train":[]}
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
        motorsInputSelect.hasFocus = False
        if "joints" in configInfo["motors"][motorSelection]:
            #select = ui.activeSelections
            #select.clear()
            product = app.activeProduct
            design = adsk.fusion.Design.cast(product)
            rootComp = design.rootComponent
            for joint in configInfo["motors"][motorSelection]["joints"]:
                #select.add(joint)
                motorsInputSelect.addSelection(joint)

# Adds Joint Selection Info into Config Object
def selectJoints(selectInput):
    if selectInput.selectionCount > 0:
        configInfo["motors"][motorSelection]["joints"] = []
        configInfo["motors"][motorSelection]["reverse"] = []
    if selectInput.selectionCount == 0 and "joints" in configInfo["motors"][motorSelection]:
        del configInfo["motors"][motorSelection]["joints"]
        del configInfo["motors"][motorSelection]["reverse"]
    # Adds Selections into corresponding joints array
    for i in range(selectInput.selectionCount):
        configInfo["motors"][motorSelection]["joints"].append(selectInput.selection(i).entity)


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
            # Motor Inputs
            if cmdInput.id.startswith("motors"):
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
            elif cmdInput.id.startswith("motor"):
                if cmdInput.id == 'motor_joints':
                    selectJoints(cmdInput)

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
            motorsInputSelect.addSelectionFilter("JointOrigins")
            motorsInputSelect.setSelectionLimits(0)

            # Reverse Joints Option
            motorsInputReverse = motorConfigInputs.addDropDownCommandInput('motor_joints_reverse', 'Reverse Joints', adsk.core.DropDownStyles.CheckBoxDropDownStyle)
            motorsInputReverse.listItems.add('Joint 1', False)
            motorsInputReverse.listItems.add('Joint 2', False)

            # Slider to Visualize Movement
            motorsInputPower = motorConfigInputs.addFloatSliderListCommandInput('motor_power', 'Test Movement', '', [-1, -.5, 0, .5, 1])
            motorsInputPower.valueOne = 0
            motorsInputPower.setText('-1', '1 ')

            # Values for Motors
            motorConfigInputs.addIntegerSpinnerCommandInput('motor_rpm', 'Max RPM', 0, 10000, 1, 340)
            motorConfigInputs.addIntegerSpinnerCommandInput('motor_encoders', 'Encoder Ticks', 0, 10000, 1, 560)

            # Updates Motor Table
            updateTable(motorsInput, 0)

            # Tab for Servos
            tabServos = inputs.addTabCommandInput('tab_servos', 'Servos')
            tabServosInputs = tabServos.children

            # Tab for Sensors
            tabSensors = inputs.addTabCommandInput('tab_sensors', 'Sensors')
            tabSensorsInputs = tabSensors.children

            # Tab for Drive Train
            tabDrive = inputs.addTabCommandInput('tab_drvie', 'Drive Train')
            tabDriveInputs = tabDrive.children

        except:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()


def runConfig():
    global app, ui
    app = adsk.core.Application.get()
    ui = app.userInterface

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