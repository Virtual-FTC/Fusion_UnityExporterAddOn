#Author-
#Description-

import adsk.core, adsk.fusion, adsk.cam, traceback

from . import RobotConfig
from . import MeshExporter

app = None
ui = adsk.core.UserInterface.cast(None)
customEventID = 'Phase2-MeshThread'
customEvent = None

_handlers = []
        
        
def run(context):
    global ui
    global app
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        
        # Opening Statement
        statement = '''Welcome to the Unity Exporter for the Virtual Robot Simulator!

This AddOn will take your currently saved CAD File and convert it into an exportable file which can be uploaded to the Simulator.

The First Phase is where you will be able to input info on motors, servos, and sensors which will be added onto the final file.

The Second Phase will convert your CAD File into a simplified mesh for quicker upload speeds.

Finally, the exportable file will be available which you can then upload to the Virtual Robot Simulator where Game Element specific info can be added and saved as well.

If you experience any issues, feel free to reach out!
                    '''

        results = ui.messageBox(statement, "UNITY EXPORTER INFO", 1)
        if results == 1:
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

        #Clone Current Document
        data_orig = app.activeDocument.dataFile.copy(app.activeDocument.dataFile.parentFolder)
        data_orig.name = "Unity Export"
        app.documents.open(data_orig)

        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        design.designType = 0

        # Register the custom event and connect the handler.
        global customEvent
        customEvent = app.registerCustomEvent(customEventID)
        onThreadEvent = ConfigDone()
        customEvent.add(onThreadEvent)
        _handlers.append(onThreadEvent)

        adsk.autoTerminate(False)

        # Runs PHASE ONE Script
        RobotConfig.runConfig()
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            adsk.terminate()


# The event handler that responds to the custom event being fired.
# This is in order to run config back on the main thread
class ConfigDone(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            #return
            # Runs PHASE TWO Script
            cancelled = MeshExporter.runMesh()
            if cancelled:
                ui.messageBox("Successfully Cancelled Task")
            adsk.terminate()
        except:
            if ui:
                ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))

# Clean up Handlers
def stop(context):
    try:
        app.unregisterCustomEvent(customEventID)
        if _handlers.count:
            customEvent.remove(_handlers[0])
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))