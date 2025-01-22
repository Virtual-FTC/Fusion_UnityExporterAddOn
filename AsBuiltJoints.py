import adsk.core, adsk.fusion

# Script to save AsBuiltJoint info
# This is needed as designType needs to be 0 which breaks asBuiltJoints

savedJointInfo = {}

def saveJointInfo():

    class LimitInfo:
        pass

    class MotionInfo:
        def __init__(self):
            self.rotationLimits = LimitInfo()
            self.slideLimits = LimitInfo()

    class JointInfo:
        def __init__(self):
            self.jointMotion = MotionInfo()

    # Gather all asBuiltJoints
    app = adsk.core.Application.get()
    ui = app.userInterface
    design = adsk.fusion.Design.cast(app.activeProduct)
    rootComp = design.rootComponent

    asBuiltJoints = rootComp.allAsBuiltJoints
    for asBuiltJoint in asBuiltJoints:

        # Check if Valid and Not Supressed
        if asBuiltJoint.isSuppressed:
            continue
        try:
            asBuiltJoint.occurrenceOne
            asBuiltJoint.occurrenceTwo
        except:
            continue
        
        # Stores all Joint Info for Use Later
        jointInfo = JointInfo()
        jointInfo.jointMotion.jointType = int(asBuiltJoint.jointMotion.jointType)

        if asBuiltJoint.jointMotion.jointType == 1:
            jointInfo.jointMotion.rotationAxisVector = asBuiltJoint.jointMotion.rotationAxisVector.copy()
            jointInfo.jointMotion.rotationLimits.isMaximumValueEnabled = asBuiltJoint.jointMotion.rotationLimits.isMaximumValueEnabled
            jointInfo.jointMotion.rotationLimits.isMinimumValueEnabled = asBuiltJoint.jointMotion.rotationLimits.isMinimumValueEnabled
            jointInfo.jointMotion.rotationLimits.maximumValue = asBuiltJoint.jointMotion.rotationLimits.maximumValue
            jointInfo.jointMotion.rotationLimits.minimumValue = asBuiltJoint.jointMotion.rotationLimits.minimumValue
            jointInfo.jointMotion.rotationValue = asBuiltJoint.jointMotion.rotationValue

        elif asBuiltJoint.jointMotion.jointType == 2:
            jointInfo.jointMotion.slideDirectionVector = asBuiltJoint.jointMotion.slideDirectionVector.copy()
            jointInfo.jointMotion.slideLimits.isMaximumValueEnabled = asBuiltJoint.jointMotion.slideLimits.isMaximumValueEnabled
            jointInfo.jointMotion.slideLimits.isMinimumValueEnabled = asBuiltJoint.jointMotion.slideLimits.isMinimumValueEnabled
            jointInfo.jointMotion.slideLimits.maximumValue = asBuiltJoint.jointMotion.slideLimits.maximumValue
            jointInfo.jointMotion.slideLimits.minimumValue = asBuiltJoint.jointMotion.slideLimits.minimumValue
            jointInfo.jointMotion.slideValue = asBuiltJoint.jointMotion.slideValue

        asBuiltJoint.timelineObject.rollTo(True)

        jointInfo.occurrenceOne = asBuiltJoint.occurrenceOne
        jointInfo.occurrenceTwo = asBuiltJoint.occurrenceTwo
        jointInfo.geometryOrOriginOne = asBuiltJoint.geometry
        jointInfo.geometryOrOriginTwo = asBuiltJoint.geometry
        jointInfo.name = asBuiltJoint.name

        design.timeline.moveToEnd()

        # Store Info
        jointInfo.storedJoint = True

        savedJointInfo[asBuiltJoint.entityToken] = jointInfo