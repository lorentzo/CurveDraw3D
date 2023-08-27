
# Author: Lovro Bosnar
# Date: 08.08.2023.

# Blender: 3.6.1.

# TODO:


# 2. Spawn spheres in BB flying around like brownian movement
#     + enhance movement, material, size, shape
#     + collisions, change color when collide, stick when collide mmmmmmmm 0.0
#     + https://www.youtube.com/watch?v=rIhXHSdMWmc&ab_channel=CGPython
#     + metaball CSG? https://www.youtube.com/watch?v=syvhbxPE3zI&t=1s&ab_channel=JoshGambrell
# 2. More thicker bevel? Special shape? Animation? Idea: https://www.youtube.com/watch?v=CSre9wCJoWc&ab_channel=AlbertoCordero
# 6. Scenes:
#     + Emissive mballs flowing around splines - cycles
#     + Blinking splines in dark env (designer canvas in the back) - cycles
#     + Emissive blur env, splines grow in mballs flow field - EEVEE multiple camera view - camera DOF, changing sharpness
#     + close loop growth - EEVEE

import bpy
import mathutils
import bmesh
import numpy as np

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

def create_material(mat_id, mat_type, color=mathutils.Color((1.0, 0.5, 0.1)), emission_intensity=10):

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
        nodes["Emission"].inputs[1].default_value = emission_intensity

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

def animate_curve_thickness(curve, frame_start, frame_end, thickness_min, thickness_max, start_thickness=0.0):
    curve.data.bevel_depth = start_thickness
    curve.data.keyframe_insert(data_path="bevel_depth", frame=frame_start)
    curve.data.bevel_depth = lerp(mathutils.noise.random(), thickness_min, thickness_max)
    curve.data.keyframe_insert(data_path="bevel_depth", frame=frame_end)

# https://behreajj.medium.com/scripting-curves-in-blender-with-python-c487097efd13
def set_animation_fcurve(base_object, option='BOUNCE'):
    fcurves = base_object.data.animation_data.action.fcurves
    for fcurve in fcurves:
        for kf in fcurve.keyframe_points:
            # Options: ['CONSTANT', 'LINEAR', 'BEZIER', 'SINE',
            # 'QUAD', 'CUBIC', 'QUART', 'QUINT', 'EXPO', 'CIRC',
            # 'BACK', 'BOUNCE', 'ELASTIC']
            kf.interpolation = option
            # Options: ['AUTO', 'EASE_IN', 'EASE_OUT', 'EASE_IN_OUT']
            kf.easing = 'EASE_OUT'

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

def generate_n_gradient_colors_with_same_random_hue(n=10, input_hue=mathutils.noise.random()):
    rand_cols = []
    for i in range(n):
        col = mathutils.Color()
        col.hsv = (input_hue, mathutils.noise.random(), mathutils.noise.random())
        rand_cols.append(col)
    return rand_cols

def spawn_and_animate_spheres_in_bb(obj, n_spheres, r_min=1, r_max=3, mat_type="diffuse", diff_col=mathutils.Color((1,1,1)), emission_intensity=10, movement_intensity=5.0, n_frames=100):
    # Find BB corners in world space.
    bb = obj.bound_box
    bb_vecs = []
    world_translation = obj.matrix_basis.to_translation()
    world_rotation = obj.matrix_basis.to_euler()
    for bb_i in bb:
        bb_vec = mathutils.Vector((bb_i[0], bb_i[1], bb_i[2])) # BB in local space.
        bb_vec += world_translation
        bb_vec.rotate(world_rotation)
        bb_vecs.append(bb_vec)
        #bpy.ops.mesh.primitive_ico_sphere_add(radius=1, enter_editmode=False, align='WORLD', location=bb_i, scale=(1, 1, 1))
        #bpy.context.selected_objects[0].name = str(bb_vec[0]) + "_" + str(bb_vec[1]) + "_" + str(bb_vec[2])
    #bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=bb_vecs[0], scale=(1, 1, 1))
    #bpy.ops.mesh.primitive_cube_add(size=2, enter_editmode=False, align='WORLD', location=bb_vecs[-2], scale=(1, 1, 1))
    # Spawn spheres.
    mballs = []
    for i in range(n_spheres):
        loc_x = lerp(mathutils.noise.random(), bb_vecs[0].x, bb_vecs[-2].x)
        loc_y = lerp(mathutils.noise.random(), bb_vecs[0].y, bb_vecs[-2].y)
        loc_z = lerp(mathutils.noise.random(), bb_vecs[0].z, bb_vecs[-2].z)
        radius = lerp(mathutils.noise.random(), r_min, r_max)
        bpy.ops.object.metaball_add(type='BALL', radius=radius, enter_editmode=False, align='WORLD', location=mathutils.Vector((loc_x, loc_y, loc_z)), scale=(1, 1, 1))
        mball = bpy.context.selected_objects[0]
        mballs.append(mball)
        mball.keyframe_insert("location", frame=0)
        # Add material.
        if mat_type == "emission":
            ei = lerp(mathutils.noise.random(), 5, 10)
            mat = create_material(mball.name+"_mat", "emission", mathutils.Color((1, 1, 1)), ei)
        else:
            mat = create_material(mball.name+"_mat", "diffuse", diff_col)
        mball.data.materials.append(mat)
    # Animate.
    keyframe_delta = 10
    curr_frame = 10
    while curr_frame <= n_frames:
        for mball in mballs:
            mball.location += mathutils.noise.noise_vector(mball.location) * movement_intensity
            mball.keyframe_insert("location", frame=curr_frame)
        curr_frame += keyframe_delta

    

def main():

    # Parameters.
    curve_drawing_collection_name = "curve_drawing_collection"
    n_frames = 300

    # Sphere parameters.
    n_spheres = 30
    r_min = 5
    r_max = 9
    mat_type = "emission"
    diff_col = mathutils.Color((1,1,1))
    emission_intensity = 10.0
    movement_intensity = 10.0

    # Curve parameters
    n_instances_per_drawing = 80
    translation_rand_strength = 50.0
    bevel_thickening_period = 10
    chance_of_emissive_curves = 0.3
    

    array_of_instance_arrays = []
    rand_5_colors = generate_5_random_colors_that_fit()
    curr_draw_curve_idx = 0
    for curve_drawing in bpy.data.collections[curve_drawing_collection_name].all_objects:

        # Create mballs in BB of current draw curve input. 
        spawn_and_animate_spheres_in_bb(curve_drawing, n_spheres=n_spheres, r_min=r_min, r_max=r_max, mat_type=mat_type, diff_col=diff_col, emission_intensity=emission_intensity, movement_intensity=movement_intensity, n_frames=n_frames)

        # Generate random color for current draw curve input.
        hue = rand_5_colors[curr_draw_curve_idx % 5].h
        rand_colors = generate_n_gradient_colors_with_same_random_hue(n_instances_per_drawing, hue)

        instance_array = []
        for i_instance_per_drawing in range(n_instances_per_drawing):
            # Create copy.
            drawing_instance = copy_obj(curve_drawing, "curve_drawing_instance")
            # Randomize translation of whole curve.
            drawing_instance.location += mathutils.Vector((mathutils.noise.random()-0.5, mathutils.noise.random()-0.5, mathutils.noise.random()-0.5)) * translation_rand_strength
            # Preturb curve points.
            perturb_curve_points(drawing_instance, perturb_scale=1, perturb_strength=1, n_octaves=2, amplitude_scale=1, frequency_scale=2)
            # Add material.
            if mathutils.noise.random() < chance_of_emissive_curves:
                emission_intensity = lerp(mathutils.noise.random(), 5.0, 10.0)
                rand_col_idx = int(mathutils.noise.random() * len(rand_colors))
                mat = create_material(drawing_instance.name+"_mat", "emission", rand_colors[rand_col_idx], emission_intensity)
            else:
                rand_col_idx = int(mathutils.noise.random() * len(rand_colors))
                mat = create_material(drawing_instance.name+"_mat", "diffuse", rand_colors[rand_col_idx])
            drawing_instance.data.materials.append(mat)
            # Animate growth.
            end_mapping_animation = lerp(mathutils.noise.random(), 0.7, 1.0)
            start_mapping_animation = lerp(mathutils.noise.random(), 0.01, 0.1)
            animate_curve_growth(drawing_instance, frame_start=0, frame_end=n_frames, growth_factor_end=end_mapping_animation, start_growth=start_mapping_animation)
            set_animation_fcurve(drawing_instance, option="CUBIC")
            # Animate thickening.
            # Set bevel certain bevel depth.
            drawing_instance.data.bevel_depth = mathutils.noise.random() * 2.1 + 0.1
            drawing_instance.data.keyframe_insert(data_path="bevel_depth", frame=0)
            # Animate growing and shrinking.
            curr_frame_bevel = 30
            delta_frame_bevel = int(n_frames / bevel_thickening_period)
            for i in range(bevel_thickening_period):
                thickness_min = drawing_instance.data.bevel_depth * 0.8
                thickness_max = drawing_instance.data.bevel_depth * 1.2
                animate_curve_thickness(drawing_instance, frame_start=curr_frame_bevel, frame_end=curr_frame_bevel+delta_frame_bevel, thickness_min=thickness_min, thickness_max=thickness_max, start_thickness=drawing_instance.data.bevel_depth)
                curr_frame_bevel += delta_frame_bevel
            # Store instance.
            instance_array.append(drawing_instance)
        array_of_instance_arrays.append(instance_array)

        curr_draw_curve_idx += 1

#
# Script entry point.
#
if __name__ == "__main__":
    main()