#Author-
#Description-

import os
from pydoc import doc
from xml.dom import minidom
import adsk.core, adsk.fusion, adsk.cam, traceback

from . import RobotConfig
from . import MeshExporter

app = None
ui = adsk.core.UserInterface.cast(None)
customEventID = 'Phase2-MeshThread'
customEvent = None

_handlers = []

docName = ""

        
def run(context):
    global ui
    global app
    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        
        # Opening Statement
        statement = '''Welcome to the Unity Exporter for the Virtual Robot Simulator!

**MAKE SURE YOU HAVE ALREADY RIGGED UP JOINTS ON YOUR ROBOT BEFORE GOING THROUGH THIS PROCESS!**

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
        global docName
        docName = app.activeDocument.name
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
        #app.fireCustomEvent(customEventID, '') 
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

def finalExport():
    global docName, app, ui
    app = adsk.core.Application.get()
    ui  = app.userInterface

    # DocName does not save past RobotConfig UI system
    if not docName:
        docName = app.activeDocument.name

    progressBar = ui.createProgressDialog()
    progressBar.show("Converting Robot File", "Step 4: Creating URDF File...", 0, 1, 0)
    progressBar.progressValue = 1

    # Creates XML URDF File
    root = minidom.Document()
    robot = root.createElement('robot')
    robot.setAttribute('name', docName)
    root.appendChild(robot)

    product = app.activeProduct
    design = adsk.fusion.Design.cast(product)
    rootComp = design.rootComponent

    attributes = root.createElement('attributes')
    robot.appendChild(attributes)

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
        # <<Taken from Mesh Exporter>> (Should be modified into method for all to use)
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
            ui.messageBox("Whoops! It seems Joint: \"" + revJoint.name + "\" is connected to a currently not supported piece of Geometry! In a future update this may be fixed.")
            joint.entityOne.body.parentComponent
        baseComp = rootComp.allOccurrencesByComponent(baseComp).item(0)
        if baseComp:
            transform = baseComp.transform2
            transform.invert()
            transform.transformBy(jointsOcc[1].transform2)
            jointsOrigin.transformBy(transform)
        # <<Taken from Mesh Exporter>>
        origin = root.createElement('origin')
        origin.setAttribute('xyz', str(jointsOrigin.x) + " " + str(jointsOrigin.y) + " " + str(jointsOrigin.z))
        jntXML.appendChild(origin)
        # Checks if a wheel joint
        for wheeltype, joints in RobotConfig.configInfo["drive_train"].items():
            for jntConfig in joints:
                if revJoint.name == "unityjoint_" + str(jntConfig):
                    wheelXML = root.createElement('wheel')
                    wheelXML.setAttribute('type', wheeltype)
                    jntXML.appendChild(wheelXML)
                    revJoint.occurrenceOne.component.name = "wheel_" + revJoint.occurrenceOne.name[10:-2]
                    child.setAttribute('link', revJoint.occurrenceOne.name[:-2])
                    break
        # Revolute (Limited) or Continuous
        if revJoint.jointMotion.rotationLimits.isMaximumValueEnabled:
            jntXML.setAttribute('type', 'revolute')
            limit = root.createElement('limit')
            limit.setAttribute('upper', str(revJoint.jointMotion.rotationLimits.maximumValue))
            limit.setAttribute('lower', str(revJoint.jointMotion.rotationLimits.minimumValue))
            jntXML.appendChild(limit)
        else:
            jntXML.setAttribute('type', 'continuous')

    # Adds Motors and their corresponding info
    for motor in RobotConfig.configInfo["motors"]:
        mtrXML = root.createElement('motor')
        mtrXML.setAttribute('name', motor['name'])
        robot.appendChild(mtrXML)
        powered = root.createElement('powered')
        # Finds Selected Joints and their info
        if len(motor['joints']) > 0:
            jointsStr = ""
            for joint in motor['joints']:
                jointsStr += "unityjoint_" + str(joint) + " "
                # Inverses Axis if set in Reverse
                if joint in motor['reverse']:
                    for jntXML in root.getElementsByTagName('joint'):
                        if jntXML.getAttribute('name') == "unityjoint_" + str(joint):
                            axisNode = jntXML.getElementsByTagName('axis')[0]
                            axis = [float(i) for i in axisNode.getAttribute('xyz').split(' ')]
                            axisNode.setAttribute('xyz', str(-axis[0]) + ' ' + str(-axis[1]) + ' ' + str(-axis[2]))
                            break
            # Adds Joints to info
            powered.setAttribute('joints', jointsStr[:-1])
            mtrXML.appendChild(powered)
        attributes = root.createElement('attributes')
        attributes.setAttribute('gearRatio', str(motor['ratio']))
        attributes.setAttribute('maxRPM', str(motor['maxRPM']))
        attributes.setAttribute('encoderTicksPerRev', str(motor['ticksPerRev']))
        mtrXML.appendChild(attributes)

    # Store Meshes
    ui.messageBox("Select Location to Store Folder of Robot Data", "Almost Finished!")

    folderDia = ui.createFolderDialog()
    folderDia.title = "Select Location to Store Folder of Robot Data"
    dlgResults = folderDia.showDialog()

    if dlgResults != 0:
        return

    exportPath = folderDia.folder + "/" + docName

    if not os.path.exists(exportPath):
        os.makedirs(exportPath)

    xml_string = root.toxml()

    f = open(exportPath + "/robotfile.urdf", "w")
    f.write(xml_string)
    f.close()

    '''
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
    '''

    app.activeDocument.save("")
    progressBar.hide()

    ui.messageBox("Finished!\nFinal Step: Go into options to export Robot as an FBX File.")

    return

# Clean up Handlers
def stop(context):
    try:
        app.unregisterCustomEvent(customEventID)
        if _handlers.count:
            customEvent.remove(_handlers[0])
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))