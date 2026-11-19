import bpy, bmesh, math
from mathutils import Vector

bpy.ops.wm.read_factory_settings(use_empty=True)

def lerp(a, b, t): return a + (b - a) * t
def clamp(v, a=0.0, b=1.0): return max(a, min(b, v))
def interp(keys, vals, t):
    for i in range(len(keys) - 1):
        if keys[i] <= t <= keys[i + 1]:
            u = (t - keys[i]) / (keys[i + 1] - keys[i])
            u = u * u * (3 - 2 * u)
            return lerp(vals[i], vals[i + 1], u)
    return vals[-1]

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c) + (1.0,)

def make_mat(name, rough=0.8, use_vc=True, color=None, spec=0.3):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs: bsdf.inputs['Specular IOR Level'].default_value = spec
    if use_vc:
        ca = nt.nodes.new('ShaderNodeVertexColor'); ca.layer_name = 'Col'
        nt.links.new(ca.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = srgb(color)
    return m

def mesh_obj(name, bm, mat, parent=None, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    if 'Col' in me.color_attributes:
        me.color_attributes.active_color_name = 'Col'; me.color_attributes.render_color_index = me.color_attributes.find('Col')
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.location = loc
    if parent: ob.parent = parent
    return ob

def sstep(a, b, x):
    t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t)
def mix(c1, c2, w): return tuple(lerp(c1[i], c2[i], w) for i in range(4))
def color_faces(bm, fn):
    lay = bm.loops.layers.color.get('Col') or bm.loops.layers.color.new('Col')
    bm.normal_update()
    for f in bm.faces:
        for l in f.loops: l[lay] = fn(l.vert.co, l.vert.normal)

def sphere(seg, ring, r=1.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=r)
    return bm

def build(prefix, P):
    root = bpy.data.objects.new(prefix, None); bpy.context.collection.objects.link(root)
    feather = make_mat(prefix + '_Feather', 0.85, spec=0.25)
    beakm = make_mat(prefix + '_Beak', 0.45)
    feetm = make_mat(prefix + '_Feet', 0.7, False, P['feet'])
    eyem = make_mat(prefix + '_Eye', 0.12, False, '#0b0b0e', spec=0.8)
    DARK, WHITE = srgb(P['dark']), srgb(P['white'])

    # ---- body (lathe-like egg, front = -Y) ----
    bm = sphere(40, 30)
    z0, H = P['z0'], P['H']
    for v in bm.verts:
        x, y, z = v.co
        t = (z + 1) / 2
        rr = math.sqrt(max(0.0, 1 - z * z))
        R = interp([0, .04, .14, .34, .55, .76, .9, 1], P['prof'], t)
        nx, ny = (x / rr, y / rr) if rr > 1e-6 else (0, 0)
        fb = P['front'] if ny < 0 else P['back']
        chest = 1 + P['chest'] * math.exp(-((t - .5) / .18) ** 2) * max(0, -ny)
        X = nx * R * P['wide']
        Y = ny * R * fb * chest - P['lean'] * t * t
        v.co = Vector((X, Y, z0 + t * H))
    bm.normal_update()
    zw = P['white_top']
    def body_col(c, n):
        if P['chick']:
            return mix(WHITE, DARK, sstep(zw - .05, zw + .05, c.z))
        front = -n.y
        th = -0.15 + 0.8 * sstep(zw - 0.13, zw, c.z)
        th -= 0.6 * sstep(z0 + .1, z0, c.z)
        w = sstep(-0.09, 0.09, front - th) * sstep(zw + .025, zw - .025, c.z)
        return mix(DARK, WHITE, w)
    color_faces(bm, body_col)
    body = mesh_obj(prefix + '_Body', bm, feather, root)

    # ---- tail ----
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=P['tail'], radius2=0.004, depth=P['tail'] * 3.2)
    for v in bm.verts: v.co.x *= 1.4; v.co.y *= .45
    bm.normal_update(); color_faces(bm, lambda c, n: DARK)
    tail = mesh_obj(prefix + '_Tail', bm, feather, root, (0, P['tailY'], z0 + 0.05))
    tail.rotation_euler = (math.radians(-118), 0, 0)

    # ---- head (pivot at neck) ----
    neck = Vector((0, -P['lean'] * .9, z0 + H * .93))
    head = bpy.data.objects.new(prefix + '_Head', None); bpy.context.collection.objects.link(head)
    head.parent = root; head.location = neck
    hr = P['head_r']
    bm = sphere(34, 26, hr)
    for v in bm.verts:
        v.co.x *= .93; v.co.y *= 1.08; v.co.z *= .96
        if v.co.y < 0: v.co.z -= (-v.co.y) * .12   # forehead slope
    bm.normal_update()
    hc = Vector((0, -0.01, hr * .55))
    eyes = []
    for s in (-1, 1):
        d = Vector((s * .62, -.62, .30)).normalized(); eyes.append(d)
    def head_col(c, n):
        d = Vector((c.x / .93, c.y / 1.08, c.z / .96)).normalized()
        w = 0
        if False:
            for e in eyes:
                ang = math.degrees(d.angle(e)); w = max(w, sstep(P['ring_deg'] + 2.5, P['ring_deg'] - 2.5, ang))
        base = DARK
        if P['chick']: base = mix(srgb(P['dark2']), DARK, sstep(-hr * .5, hr * .3, c.z))
        return mix(base, WHITE, w)
    color_faces(bm, head_col)
    hmesh = mesh_obj(prefix + '_HeadMesh', bm, feather, head, hc)
    # eyes
    for e in eyes:
        bm = sphere(12, 8, P['eye_r'])
        p = Vector((e.x * hr * .93, e.y * hr * 1.08, e.z * hr * .96))
        p = p + e * (-P['eye_r'] * .25)
        mesh_obj(prefix + '_Eye', bm, eyem, head, hc + p)
        if P['eyering']:
            bm = bmesh.new()
            bmesh.ops.create_circle(bm, cap_ends=False, segments=20, radius=1)
            # build a flat annulus
            bm.free(); bm = bmesh.new()
            ri, ro = P['eye_r'] * 1.05, P['eye_r'] * 2.1
            inner = []; outer = []
            for i in range(24):
                a = i / 24 * math.tau
                inner.append(bm.verts.new((math.cos(a) * ri, math.sin(a) * ri * 1.0, 0)))
                outer.append(bm.verts.new((math.cos(a) * ro * 1.1, math.sin(a) * ro * .95, -ro * .25)))
            for i in range(24):
                j = (i + 1) % 24
                bm.faces.new((inner[i], inner[j], outer[j], outer[i]))
            bm.normal_update(); color_faces(bm, lambda c, n: WHITE)
            ring = mesh_obj(prefix + '_EyeRing', bm, feather, head, hc + p + e * 0.001)
            ring.rotation_mode = 'QUATERNION'
            ring.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(e)
    # beak
    bm = bmesh.new()
    L = P['beak_len']
    bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=P['beak_r'], radius2=P['beak_r'] * .18, depth=L)
    for v in bm.verts:
        v.co.x *= .8
        tz = (v.co.z + L / 2) / L
        v.co.y += -0.004 * math.sin(tz * math.pi)  # slight hook
    bm.normal_update()
    bc1, bc2 = srgb(P['beak']), srgb(P['beak_base'])
    color_faces(bm, lambda c, n: bc2 if (c.z < -L * .32 and n.z > -0.2 and P['beak_base'] != P['beak']) else bc1)
    beak = mesh_obj(prefix + '_Beak', bm, beakm, head, hc + Vector((0, -hr * .98 - L * .36, -hr * .2)))
    beak.rotation_euler = (math.radians(90 + 14), 0, 0)

    # ---- flippers (pivot at shoulder) ----
    for s, nm in ((-1, 'L'), (1, 'R')):
        piv = bpy.data.objects.new(prefix + '_Flipper' + nm, None); bpy.context.collection.objects.link(piv)
        piv.parent = root
        sz = z0 + H * .66
        piv.location = (s * P['shoulder'], -0.005, sz)
        bm = sphere(16, 12, 1)
        fl = P['flip_len']
        for v in bm.verts:
            x, y, z = v.co
            t = (1 - z) / 2  # 0 top, 1 tip
            w = P['flip_w'] * (1 - .55 * t) * (1 + .25 * math.sin(t * 3))
            v.co = Vector((x * .016, y * w, -t * fl))
            v.co.y += 0.012 * t
        bm.normal_update()
        def fcol(c, n, s=s):
            out = n.x * s
            w = sstep(-0.1, -0.4, out) * sstep(-P['flip_w'] * .5, -P['flip_w'] * .2, c.y)
            return mix(DARK, WHITE if not P['chick'] else DARK, w)
        color_faces(bm, fcol)
        m = mesh_obj(prefix + '_FlipperMesh' + nm, bm, feather, piv, (s * 0.012, 0, 0))
        piv.rotation_euler = (0, s * math.radians(-P['flip_out']), 0)

    # ---- feet (pivot at ankle) ----
    for s, nm in ((-1, 'L'), (1, 'R')):
        piv = bpy.data.objects.new(prefix + '_Foot' + nm, None); bpy.context.collection.objects.link(piv)
        piv.parent = root; piv.location = (s * P['foot_x'], -0.02, z0 + 0.02)
        bm = bmesh.new()
        fsc = P['foot']
        for a in (-24, 0, 24):
            t = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1)
            vs = [e for e in t['verts']]
            ra = math.radians(a + s * 6)
            for v in vs:
                x, y, z = v.co
                x, y, z = x * .013 * fsc, y * .05 * fsc, z * .009 * fsc
                y -= .045 * fsc
                X = x * math.cos(ra) - y * math.sin(ra); Y = x * math.sin(ra) + y * math.cos(ra)
                v.co = Vector((X, Y, z - .012))
        t = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1)
        for v in t['verts']: v.co = Vector((v.co.x * .028 * fsc, v.co.y * .03 * fsc - .01, v.co.z * .02 * fsc - .006))
        bm.normal_update()
        mesh_obj(prefix + '_FootMesh' + nm, bm, feetm, piv)
    return root

ADULT = dict(chick=False, dark='#16181f', white='#f1efe8', dark2='#16181f', feet='#e6b1aa',
             beak='#232020', beak_base='#b8463a', z0=0.03, H=0.52,
             prof=[0, .10, .155, .178, .165, .125, .088, .062], wide=1.0, front=1.12, back=.92, chest=.12, lean=0.03,
             white_top=0.43, tail=.035, tailY=.13, head_r=.093, eyering=True, ring_deg=11.5, eye_r=.0095,
             beak_len=.075, beak_r=.019, shoulder=.158, flip_len=.24, flip_w=.05, flip_out=8,
             foot_x=.055, foot=1.0)
CHICK = dict(chick=True, dark='#5c5b60', white='#b0aaa3', dark2='#4a494e', feet='#3a3536',
             beak='#1e1d1f', beak_base='#1e1d1f', z0=0.02, H=0.33,
             prof=[0, .10, .16, .182, .172, .14, .10, .07], wide=1.05, front=1.05, back=1.0, chest=.06, lean=0.0,
             white_top=0.30, tail=.02, tailY=.14, head_r=.082, eyering=False, ring_deg=0, eye_r=.011,
             beak_len=.04, beak_r=.013, shoulder=.17, flip_len=.13, flip_w=.035, flip_out=14,
             foot_x=.06, foot=.85)
build('Adult', ADULT)
c = build('Chick', CHICK); c.location.x = 0.6

def build_whale():
    root = bpy.data.objects.new('Whale', None); bpy.context.collection.objects.link(root); root.location.x = 3
    skin = make_mat('Whale_Skin', 0.5, spec=0.45)
    DARK, WHITE, MID = srgb('#34404d'), srgb('#e3e8eb'), srgb('#6b7784')
    bm = sphere(48, 34)
    for v in bm.verts:
        x, y, z = v.co
        t = (1 - z) / 2
        rr = math.sqrt(max(0.0, 1 - z * z))
        nx, ny = (x / rr, y / rr) if rr > 1e-6 else (0, 0)
        R = interp([0, .03, .1, .28, .48, .68, .84, .95, 1], [0, .045, .08, .108, .104, .074, .04, .02, .012], t)
        X = nx * R * 1.08
        Z = ny * R * .86
        if ny > 0 and t < .3: Z *= .82
        if ny < 0 and t < .45: Z *= 1.08
        v.co = Vector((X, -0.5 + t, Z))
    bm.normal_update()
    def wcol(c, n):
        t = c.y + .5
        under = sstep(0.05, -0.35, n.z)
        if t < .5:
            w = under * sstep(.5, .35, t)
            groove = 1 if (math.sin(math.atan2(c.x, -c.z) * 46) > .55 and under > .5 and t > .04) else 0
            col = mix(DARK, WHITE, w)
            return mix(col, MID, groove * .7)
        return mix(DARK, MID, under * .5)
    color_faces(bm, wcol)
    mesh_obj('Whale_Body', bm, skin, root)
    # tubercles on head
    for i in range(10):
        t = .04 + i * .022; s = (-1) ** i
        bm = sphere(8, 6, .006 + .002 * (i % 3)); color_faces(bm, lambda c, n: DARK)
        R = interp([0, .03, .1, .28], [0, .045, .08, .108], t)
        mesh_obj('Whale_Knob', bm, skin, root, (s * R * .35 * ((i % 3) / 2 + .3), -0.5 + t, R * .7))
    # dorsal fin
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=.03, radius2=.003, depth=.04)
    for v in bm.verts: v.co.x *= .35; v.co.y += (v.co.z + .02) * .6
    bm.normal_update(); color_faces(bm, lambda c, n: DARK)
    mesh_obj('Whale_Dorsal', bm, skin, root, (0, .2, .08))
    # pectoral fins
    for sgn, nm in ((-1, 'L'), (1, 'R')):
        piv = bpy.data.objects.new('Whale_Fin' + nm, None); bpy.context.collection.objects.link(piv); piv.parent = root
        piv.location = (sgn * .085, -0.22, -.05)
        bm = sphere(16, 10, 1)
        for v in bm.verts:
            x, y, z = v.co; t = (x + 1) / 2
            w = .035 * (1 - .6 * t) * (1 + .3 * math.sin(t * 9))
            v.co = Vector((sgn * t * .33, y * w + t * t * .06, z * .007))
        bm.normal_update(); color_faces(bm, lambda c, n: mix(WHITE, MID, .25 if n.z > 0 else 0))
        mesh_obj('Whale_FinMesh' + nm, bm, skin, piv)
        piv.rotation_euler = (math.radians(-10), math.radians(sgn * 28), math.radians(sgn * -25))
    # fluke
    piv = bpy.data.objects.new('Whale_Fluke', None); bpy.context.collection.objects.link(piv); piv.parent = root
    piv.location = (0, .48, 0)
    bm = sphere(24, 10, 1)
    for v in bm.verts:
        x, y, z = v.co
        X = x * .16
        Y = y * .045 + abs(x) ** 1.6 * .07 + .03
        if abs(x) < .15: Y -= .01
        v.co = Vector((X, Y, z * .008))
    bm.normal_update(); color_faces(bm, lambda c, n: WHITE if n.z < -.2 else DARK)
    mesh_obj('Whale_FlukeMesh', bm, skin, piv)
    return root
build_whale()

bpy.ops.export_scene.gltf(filepath='assets/penguins.glb', export_format='GLB',
                          export_apply=True, export_vertex_color='ACTIVE', export_all_vertex_colors=False)
print('exported')
