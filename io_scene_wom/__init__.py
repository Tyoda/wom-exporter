import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty

from bpy_extras.io_utils import ExportHelper

bl_info = {
    "name": "WOM exporter for Wurm Unlimited",
    "author": "Tyoda",
    "version": (0, 0, 1),
    "blender": (3, 5, 1),
    "api": 38691,
    "location": "File > Import-Export",
    "description": ("Export WOM scenes for use within Wurm Unlimited. Eventually it should support animations."),
    "warning": "",
    "tracker_url": "https://github.com/Tyoda/wom-exporter",
    "support": "OFFICIAL",
    "category": "Import-Export"
}

if "bpy" in locals():
    import imp
    if "export_wom" in locals():
        imp.reload(export_wom)  # noqa


class CE_OT_export_dae(bpy.types.Operator, ExportHelper):
    """Selection to DAE"""
    bl_idname = "export_scene.wom"
    bl_label = "Export WOM"
    bl_options = {"PRESET"}

    filename_ext = ".wom"
    filter_glob : StringProperty(default="*.wom", options={"HIDDEN"})

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling
    object_types : EnumProperty(
        name="Object Types",
        options={"ENUM_FLAG"},
        items=(("EMPTY", "Empty", ""),
               ("CAMERA", "Camera", ""),
               ("LAMP", "Lamp", ""),
               ("ARMATURE", "Armature", ""),
               ("MESH", "Mesh", ""),
               ("CURVE", "Curve", ""),
               ),
        default={"EMPTY", "CAMERA", "LAMP", "ARMATURE", "MESH", "CURVE"},
    )

    fix_mesh_names : BoolProperty(
        name="Fix Mesh Names",
        description="Meshes will be renamed mesh_0, mesh_1...",
        default=False
    )

    use_tangent_arrays : BoolProperty(
        name="Tangent Arrays",
        description="Export Tangent and Binormal arrays "
                    "(for normal mapping).",
        default=False,
    )

    use_export_selected : BoolProperty(
        name="Selected Objects",
        description="Export only selected objects (and visible in active "
                    "layers if that applies).",
        default=False,
    )

    use_copy_images : BoolProperty(
       name="Copy Images",
       description="Copy images to same folder as .wom file",
       default=False,
    )

    use_y_is_up : BoolProperty(
        name="Y is up",
        description="Use the Y axis as up and Z as forward",
        default=False,
    )

    # use_active_layers : BoolProperty(
    #     name="Active Layers",
    #     description="Export only objects on the active layers.",
    #     default=True,
    # )

    # use_anim : BoolProperty(
    #     name="Export Animation",
    #     description="Export keyframe animation",
    #     default=False,
    # )

    # use_anim_action_all : BoolProperty(
    #     name="All Actions",
    #     description=("Export all actions for the first armature found "
    #                  "in separate DAE files"),
    #     default=False,
    # )

    @property
    def check_extension(self):
        return True

    def execute(self, context):
        if not self.filepath:
            raise Exception("filepath not set")

        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "global_scale",
                                            "check_existing",
                                            "filter_glob",
                                            "xna_validate",
                                            ))

        from . import export_wom
        return export_wom.save(self, context, **keywords)


def menu_func(self, context):
    self.layout.operator(CE_OT_export_dae.bl_idname, text="WOM (.wom)")

	
def register():	 
	from bpy.utils import register_class

	register_class(CE_OT_export_dae)
	
	bpy.types.TOPBAR_MT_file_export.append(menu_func)


def unregister():	 
	from bpy.utils import unregister_class
	
	unregister_class(CE_OT_export_dae)
	
	bpy.types.TOPBAR_MT_file_export.remove(menu_func)


if __name__ == "__main__":
    register()
