import os
import shutil
import bpy
import bmesh
from mathutils import Vector
import struct
from collections import OrderedDict

SHORT_MAX_VALUE = 32767
SHORT_MIN_VALUE = -32768

INTEGER_MAX_VALUE = 2147483647
INTEGER_MIN_VALUE = -2147483648

BYTE_MAX_VALUE = 127
BYTE_MIN_VALUE = -128

FLOAT_MAX_VALUE = 3.4028235E38


class LittleEndianOutput:
    def __init__(self, path):
        self.path = path
        self.file = open(self.path, "wb")

    def write_byte(self, byte):
        if byte > BYTE_MAX_VALUE or byte < BYTE_MIN_VALUE:
            raise Exception(f'Tried to write byte that was out of range: {byte}')
        self.file.write(struct.pack('<b', byte))

    def write_float(self, floaty):
        self.file.write(struct.pack('<f', floaty))

    def write_int32(self, integer):
        if integer > INTEGER_MAX_VALUE or integer < INTEGER_MIN_VALUE:
            raise Exception(f'Tried to write integer that was out of range: {integer}')
        self.file.write(struct.pack('<i', integer))

    def write_short16(self, short):
        if short > SHORT_MAX_VALUE or short < SHORT_MIN_VALUE:
            raise Exception(f'Tried to write short that was out of range: {short}')
        self.file.write(struct.pack('<h', short))

    def write_string(self, string):
        string_bytes = bytes(string, "utf8")
        self.write_int32(len(string_bytes))
        self.file.write(string_bytes)

    def close(self):
        self.file.close()


class WOMExporter:
    class Vertex:
        __slots__ = ("vertex", "normal", "tangent", "bitangent", "color", "uv",
                     "uv2", "bones", "weights", "index")

        def __init__(self):
            self.vertex = Vector((0.0, 0.0, 0.0))
            self.normal = Vector((0.0, 0.0, 0.0))
            self.tangent = None
            self.bitangent = None
            self.color = None
            self.uv = []
            self.uv2 = Vector((0.0, 0.0))
            self.bones = []
            self.weights = []
            self.index = -1

    def write_mesh(self, output, mesh_node, name_override):
        try:
            mesh = mesh_node.data

            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            bm.free()

            has_tangents = self.config["use_tangent_arrays"]
            if has_tangents and len(mesh.uv_layers):
                try:
                    mesh.calc_tangents()
                except:
                    self.operator.report(
                        {"WARNING"},
                        "CalcTangets failed for mesh \"{}\", no tangets will be "
                        "exported.".format(mesh.name))
                    mesh.calc_normals_split()
                    has_tangents = False
            else:
                mesh.calc_normals_split()
                has_tangents = False
            output.write_byte(1 if has_tangents else 0)
            has_binormal = has_tangents
            output.write_byte(1 if has_binormal else 0)
            has_vertex_color = len(mesh.vertex_colors) != 0
            output.write_byte(1 if has_vertex_color else 0)

            name = mesh.name

            if name_override is not None and name_override != "":
                name = name_override
                print('Overriding mesh name.')
            print(f'Mesh name:\t{name}')
            output.write_string(name)

            print(f'Has tangents:\t{has_tangents}')
            print(f'Has binormals:\t{has_binormal}')
            print(f'Has colors:\t{has_vertex_color}')

            vertices_dict = OrderedDict()
            boop = 0
            for fi in range(len(mesh.polygons)):
                f = mesh.polygons[fi]
                boop += f.loop_total
                for lt in range(f.loop_total):
                    loop_index = f.loop_start + lt
                    ml = mesh.loops[loop_index]

                    if vertices_dict.get(ml.vertex_index) is None:
                        v = self.Vertex()
                        v.index = ml.vertex_index

                        mv = mesh.vertices[v.index]
                        v.vertex = Vector(mv.co)

                        for xt in mesh.uv_layers:
                            v.uv.append(Vector(xt.data[loop_index].uv))

                        if has_vertex_color:
                            v.color = Vector(mesh.vertex_colors[0].data[loop_index].color)

                        v.normal = Vector(ml.normal)

                        if has_tangents:
                            v.tangent = Vector(ml.tangent)
                            v.bitangent = Vector(ml.bitangent)

                        vertices_dict[ml.vertex_index] = v
            vertices = list(vertices_dict.values())
            vertices.sort(key=lambda x: x.index)

            vertex_count = len(vertices)
            output.write_int32(vertex_count)
            print(f'Vertices:\t{vertex_count}')

            for v in vertices:
                # position
                output.write_float(v.vertex.x)
                if self.config["use_y_is_up"]:
                    output.write_float(v.vertex.z)
                    output.write_float(v.vertex.y)
                else:
                    output.write_float(v.vertex.y)
                    output.write_float(v.vertex.z)

                # normal
                normal = v.normal
                if self.config["use_y_is_up"]:
                    temp = normal.y
                    normal.y = normal.z
                    normal.z = temp
                output.write_float(v.normal.x)
                output.write_float(v.normal.y)
                output.write_float(v.normal.z)

                # texture coordinates
                output.write_float(v.uv[0].x)
                output.write_float(1-v.uv[0].y)

                if has_vertex_color:
                    output.write_float(v.color.x)
                    output.write_float(v.color.y)
                    output.write_float(v.color.z)

                if has_tangents:
                    output.write_float(v.tangent.x)
                    output.write_float(v.tangent.y)
                    output.write_float(v.tangent.z)

                if has_binormal:
                    output.write_float(v.bitangent.x)
                    output.write_float(v.bitangent.y)
                    output.write_float(v.bitangent.z)

            faces_count = len(mesh.polygons)
            print(f'Faces:\t\t{faces_count}')
            print(f'Triangles:\t{faces_count*3}')

            good_faces = []
            skipped = 0

            for face in mesh.polygons:
                if len(face.vertices) != 3:
                    skipped += 1
                    continue
                if face.vertices[0] > SHORT_MAX_VALUE or face.vertices[1] > SHORT_MAX_VALUE or face.vertices[2] > SHORT_MAX_VALUE:
                    raise Exception(f'mesh {name} has too many vertices and can\'t be represented correctly in WOM')
                good_faces.append(face.vertices)

            if skipped > 0:
                print(f'Warning: mesh {name} has {skipped} face{"s" if skipped > 1 else ""} that\'s not a triangle. These won\'t work in wurm')

            output.write_int32(len(good_faces)*3)

            for face in good_faces:
                output.write_short16(face[0])
                if self.config["use_y_is_up"]:
                    output.write_short16(face[2])
                    output.write_short16(face[1])
                else:
                    output.write_short16(face[1])
                    output.write_short16(face[2])
        except Exception as e:
            print("Exception in mesh export:")
            print(e)
            raise e

    def write_material(self, output, material):
        try:
            texture_name = "something"
            textures = []
            for tn in material.node_tree.nodes:
                if tn.type == 'TEX_IMAGE':
                    textures.append(tn)
            if len(textures) > 0:
                texture_name = os.path.basename(textures[0].image.filepath)
                if self.config["use_copy_images"]:
                    imgpath = textures[0].image.filepath
                    if imgpath.startswith("//"):
                        imgpath = bpy.path.abspath(imgpath)
                    print("Copying image: "+imgpath)
                    basedir = os.path.dirname(self.path)
                    if not os.path.isdir(basedir):
                        os.makedirs(basedir)

                    if os.path.isfile(imgpath):
                        dstfile = os.path.join(basedir, os.path.basename(imgpath))

                        if not os.path.isfile(dstfile):
                            shutil.copy(imgpath, dstfile)
                        imgpath = os.path.basename(imgpath)
                    else:
                        print("Warning: image file not found! "+imgpath)
            else:
                print("Warning: no texture found for object!")

            output.write_string(texture_name)

            material_name = material.name
            output.write_string(material_name)

            print(f'Material name:\t"{material_name}"')
            print(f'Texture name:\t"{texture_name}"')

            is_enabled = True
            output.write_byte(1 if is_enabled else 0)

            has_emissive = False
            output.write_byte(1 if has_emissive else 0)
            if has_emissive:
                emissive = (0, 0, 0, 0)
                print(f'Emissive:\t{emissive[0]}\t{emissive[1]}\t{emissive[2]}\t{emissive[3]}')
                output.write_float(emissive[0])
                output.write_float(emissive[1])
                output.write_float(emissive[2])
                output.write_float(emissive[3])

            has_shininess = False
            output.write_byte(1 if has_shininess else 0)
            if has_shininess:
                shininess = 50
                print(f'Shininess:\t{shininess}')
                output.write_float(shininess)

            has_specular = False
            output.write_byte(1 if has_specular else 0)
            if has_specular:
                specular = (0, 0, 0, 0)
                print(f'Specular:\t{specular[0]}\t{specular[1]}\t{specular[2]}\t{specular[3]}')
                output.write_float(specular[0])
                output.write_float(specular[1])
                output.write_float(specular[2])
                output.write_float(specular[3])

            has_transparency = False
            output.write_byte(1 if has_transparency else 0)
            if has_transparency:
                transparency = (0, 0, 0, 0)
                print(f'Transparency:\t{transparency[0]}\t{transparency[1]}\t{transparency[2]}\t{transparency[3]}')
                output.write_float(transparency[0])
                output.write_float(transparency[1])
                output.write_float(transparency[2])
                output.write_float(transparency[3])
        except Exception as e:
            print("Exception in material export:")
            print(e)
            raise e

    def export(self):
        try:
            # export main file
            output = LittleEndianOutput(self.path)
            print("Starting export.")

            meshes = []
            for node in sorted(self.scene.objects, key=lambda x: x.name):
                if node.type == "MESH" and (not self.config["use_export_selected"] or node.select_get()):
                    meshes.append(node)
            output.write_int32(len(meshes))
            print(f'Exporting {len(meshes)} meshes.')

            materials = []

            for i in range(len(meshes)):
                mesh = meshes[i]
                if self.config["fix_mesh_names"]:
                    self.write_mesh(output, mesh, f'mesh_{i}')
                else:
                    self.write_mesh(output, mesh, None)

                print("hey")
                material_count = len(mesh.data.materials)
                output.write_int32(material_count)
                for i in range(material_count):
                    self.write_material(output, mesh.data.materials[0])
                print("ho")

            # joints
            num_joints = 0
            output.write_int32(num_joints)
            for i in range(num_joints):
                pass # TODO: Export joints

            for i in range(len(meshes)):
                has_skinning = False
                output.write_byte(1 if has_skinning else 0)
                if has_skinning:
                    pass # skinning exporting here
            output.close()

            print("Done exporting.")

            # export animation file(s)
            # if (self.config["use_anim"]):
            #     basedir = os.path.dirname(self.path)
            #     anim_dir = os.path.join(basedir, "anim")
            #     if not os.path.exists(anim_dir):
            #         os.makedirs(anim_dir)
            #     for anim_num in range(self.num_animations):
            #         anim_sections = [S_ASSET, S_ANIM+anim_num, S_NODES]
            #         f = open(os.path.join(anim_dir, "animation_"+str(anim_num)+".wom"), "wb")
            #         f.write(bytes("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n", "UTF-8"))
            #         f.write(bytes(
            #             "<COLLADA xmlns=\"http://www.collada.org/2005/11/COLLADASchema\" "
            #             "version=\"1.4.1\">\n", "UTF-8"))
            #
            #         for sect in anim_sections:
            #             for line in self.sections[sect]:
            #                 f.write(bytes(line + "\n", "UTF-8"))
            #
            #         f.write(bytes("<scene>\n", "UTF-8"))
            #         f.write(bytes(
            #             "\t<instance_visual_scene url=\"#{}\" />\n".format(
            #                 self.scene_name), "UTF-8"))
            #         f.write(bytes("</scene>\n", "UTF-8"))
            #         f.write(bytes("</COLLADA>\n", "UTF-8"))
        except Exception as e:
            print("Exception in export:")
            print(e)
            raise e

    __slots__ = ("operator", "scene", "last_id", "scene_name", "sections",
                 "path", "mesh_cache", "curve_cache", "material_cache",
                 "image_cache", "skeleton_info", "config", "valid_nodes",
                 "armature_for_morph", "used_bones", "wrongvtx_report",
                 "skeletons", "action_constraints", "temp_meshes", "num_animations")

    def __init__(self, path, kwargs, operator):
        self.operator = operator
        self.scene = bpy.context.scene
        self.last_id = 0
        self.scene_name = "scene"
        self.sections = {}
        self.path = path
        self.mesh_cache = {}
        self.temp_meshes = set()
        self.curve_cache = {}
        self.material_cache = {}
        self.image_cache = {}
        self.skeleton_info = {}
        self.config = kwargs
        self.valid_nodes = []
        self.armature_for_morph = {}
        self.used_bones = []
        self.wrongvtx_report = False
        self.skeletons = []
        self.action_constraints = []
        self.num_animations = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

def save(operator, context, filepath="", use_selection=False, **kwargs):
    try:
        with WOMExporter(filepath, kwargs, operator) as exp:
            exp.export()
    except Exception as e:
        print(e)
        raise e
    return {"FINISHED"}
