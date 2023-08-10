
# Author: Lovro Bosnar
# Date: 08.08.2023.

# Blender: 3.6.1.

# TODO:
# 1. Animate light blinking
# 2. Animate curve bevel shape

import bpy
import mathutils
import bmesh

# Interpolate [a,b] using factor t.
def lerp(t, a, b):
    return (1.0 - t) * a + t * b

def create_collection_if_not_exists(collection_name):
    if collection_name not in bpy.data.collections:
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection) #Creates a new collection

def add_object_to_collection(base_object, collection_name="collection"):
    create_collection_if_not_exists(collection_name)
    bpy.data.collections[collection_name].objects.link(base_object)

def copy_obj(obj, collection_name):
    obj_cpy = obj.copy()
    obj_cpy.data = obj.data.copy()
    obj_cpy.animation_data_clear()
    if collection_name == None:
        bpy.context.collection.objects.link(obj_cpy)
    else:
        add_object_to_collection(obj_cpy, collection_name)
    return obj_cpy

def perturb_curve_points(curve_obj, perturb_scale=1.0, perturb_strength=1.0, n_octaves=1, amplitude_scale=1.0, frequency_scale=1.0):
    curve_type = curve_obj.data.splines[0].type
    points = []
    if curve_type == "BEZIER":
        points = curve_obj.data.splines[0].bezier_points
    if curve_type == "POLY" or curve_type == "NURBS":
        points = curve_obj.data.splines[0].points
    first_point = True
    for point in points:
        if first_point:
            first_point = False
            continue
        point_co = mathutils.Vector((point.co[0], point.co[1], point.co[2]))       
        trans_vec = mathutils.noise.turbulence_vector(
            point_co * perturb_scale * mathutils.noise.random(), 
            n_octaves,
            False, #hard
            noise_basis='PERLIN_ORIGINAL',
            amplitude_scale=amplitude_scale,
            frequency_scale=frequency_scale) * perturb_strength
        new_point_co = point_co + trans_vec
        if curve_type == "BEZIER":
            point.co = (new_point_co[0], new_point_co[1], new_point_co[2])
        if curve_type == "POLY" or curve_type == "NURBS":
            point.co = (new_point_co[0], new_point_co[1], new_point_co[2], point.co[3]) # Note: https://blender.stackexchange.com/questions/220812/what-is-the-4th-coordinate-of-spline-points
    return curve_obj

def create_material(mat_id, mat_type, color=mathutils.Color((1.0, 0.5, 0.1))):

    mat = bpy.data.materials.get(mat_id)

    if mat is None:
        mat = bpy.data.materials.new(name=mat_id)

    mat.use_nodes = True

    if mat.node_tree:
        mat.node_tree.links.clear()
        mat.node_tree.nodes.clear()

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    output = nodes.new(type='ShaderNodeOutputMaterial')

    if mat_type == "diffuse":
        shader = nodes.new(type='ShaderNodeBsdfDiffuse')
        nodes["Diffuse BSDF"].inputs[0].default_value = color[:] + (1.0,)

    elif mat_type == "emission":
        shader = nodes.new(type='ShaderNodeEmission')
        nodes["Emission"].inputs[0].default_value = color[:] + (1.0,)
        nodes["Emission"].inputs[1].default_value = 1

    elif mat_type == "glossy":
        shader = nodes.new(type='ShaderNodeBsdfGlossy')
        nodes["Glossy BSDF"].inputs[0].default_value = color[:] + (1.0,)
        nodes["Glossy BSDF"].inputs[1].default_value = 0

    links.new(shader.outputs[0], output.inputs[0])

    return mat

def animate_curve_growth(curve, frame_start, frame_end, growth_factor_end, start_growth):
    curve.data.bevel_factor_end = start_growth
    curve.data.bevel_factor_start = 0
    curve.data.keyframe_insert(data_path="bevel_factor_end", frame=frame_start)
    curve.data.keyframe_insert(data_path="bevel_factor_end", frame=frame_start)
    curve.data.bevel_factor_end = growth_factor_end
    curve.data.keyframe_insert(data_path="bevel_factor_end", frame=frame_end)

# https://behreajj.medium.com/scripting-curves-in-blender-with-python-c487097efd13
def set_animation_fcurve(base_object, option='LINEAR'):
    fcurves = base_object.data.animation_data.action.fcurves
    for fcurve in fcurves:
        for kf in fcurve.keyframe_points:
            # Options: ['CONSTANT', 'LINEAR', 'BEZIER', 'SINE',
            # 'QUAD', 'CUBIC', 'QUART', 'QUINT', 'EXPO', 'CIRC',
            # 'BACK', 'BOUNCE', 'ELASTIC']
            kf.interpolation = option
            # Options: ['AUTO', 'EASE_IN', 'EASE_OUT', 'EASE_IN_OUT']
            kf.easing = 'AUTO'

# Based on: https://blog.federicopepe.com/en/2020/05/create-random-palettes-of-colors-that-will-go-well-together/
def generate_5_random_colors_that_fit():
    hue = int(mathutils.noise.random() * 360.0) # Random between [0,360]
    hue_op = int(mathutils.noise.random() * 180.0) # Random between [0,180]
    hues = [
        hue,
        hue - hue_op,
        hue + hue_op,
        hue - 2 * hue_op,
        hue + 2 * hue_op]
    rand_cols = []
    for i in range (5):
        col = mathutils.Color()
        col.hsv = (hues[i]/360.0, mathutils.noise.random(), mathutils.noise.random())
        rand_cols.append(col)
    return rand_cols

def generate_n_gradient_colors_with_same_hue(n=10):
    hue = mathutils.noise.random()
    rand_cols = []
    for i in range(n):
        col = mathutils.Color()
        col.hsv = (hue, mathutils.noise.random(), mathutils.noise.random())
        rand_cols.append(col)
    return rand_cols

def main():
    curve_drawing_collection_name = "curve_drawing_collection" 
    n_instances_per_drawing = 50
    instances_per_drawings = []
    for curve_drawing in bpy.data.collections[curve_drawing_collection_name].all_objects:
        instances_per_drawing = []
        rand_colors = generate_5_random_colors_that_fit()
        rand_colors = generate_n_gradient_colors_with_same_hue(10)
        for i_instance_per_drawing in range(n_instances_per_drawing):
            # Create copy with randomized transformation.
            drawing_instance = copy_obj(curve_drawing, "curve_drawing_instances")
            drawing_instance.location += mathutils.Vector((mathutils.noise.random()-0.5, mathutils.noise.random()-0.5, mathutils.noise.random()-0.5)) * 2.0
            # Preturb curve points.
            perturb_curve_points(drawing_instance, perturb_scale=0.3, perturb_strength=0.5, n_octaves=1, amplitude_scale=0.3, frequency_scale=1.5)
            # Set bevel depth.
            drawing_instance.data.bevel_depth = mathutils.noise.random() * 0.05
            # Add material.
            if mathutils.noise.random() > 0.8:
                emission_intensity = 10.0
                mat = create_material(drawing_instance.name+"_mat", "emission", mathutils.Color((emission_intensity, emission_intensity, emission_intensity)))
            else:
                rand_col_idx = int(mathutils.noise.random() * len(rand_colors))
                mat = create_material(drawing_instance.name+"_mat", "diffuse", rand_colors[rand_col_idx])
            drawing_instance.data.materials.append(mat)
            # Animate.
            end_mapping_animation = lerp(mathutils.noise.random(), 0.1, 1.0)
            animate_curve_growth(drawing_instance, frame_start=0, frame_end=200, growth_factor_end=end_mapping_animation, start_growth=0)
            set_animation_fcurve(drawing_instance, option="LINEAR")
            # Store instance.
            instances_per_drawing.append(drawing_instance)
        instances_per_drawings.append(instances_per_drawing)

#
# Script entry point.
#
if __name__ == "__main__":
    main()