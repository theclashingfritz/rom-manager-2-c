import bpy

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       IntVectorProperty,
                       BoolVectorProperty
                       )
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       )
from array import array
import os
from struct import *
import sys
import math
from shutil import copy
from pathlib import Path
from types import ModuleType
from mathutils import Vector
from mathutils import Euler
import re
from copy import deepcopy


bl_info = {
    "name": "SM64 Decomp C Level Importer",
    "description": "Import&Export levels for SM64 Decomp with Fast64",
    "author": "scuttlebug_raiser",
    "version": (1, 0, 0),
    "blender": (2, 83, 0),
    "location": "3D View > Tools",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"
}


def RotateObj(deg,obj):
    angle = obj.matrix_world.copy()
    angle.identity()
    angle = angle.to_euler()
    angle[0] = math.radians(-deg)
    r = obj.matrix_world.to_3x3()
    r.rotate(angle)
    t = obj.matrix_world.to_translation()
    r = r.to_4x4()
    I = r.copy()
    I.identity()
    #translation function removes other transformations
    obj.matrix_world = r+r.Translation(t)-I

def Parent(parent,child):
    parent.select_set(True)
    child.select_set(True)
    bpy.context.view_layer.objects.active = parent
    bpy.ops.object.parent_set()
    parent.select_set(False)
    child.select_set(False)

def EvalMacro(line):
    scene=bpy.context.scene
    if scene.LevelImp.Version in line:
        return False
    if scene.LevelImp.Target in line:
        return False
    return True

Num2LevelName = {
    4:'bbh',
    5:"ccm",
    7:'hmc',
    8:'ssl',
    9:'bob',
    10:'sl',
    11:'wdw',
    12:'jrb',
    13:'thi',
    14:'ttc',
    15:'rr',
    16:"castle_grounds",
    17:'bitdw',
    18:'vcutm',
    19:'bitfs',
    20:'sa',
    21:'bits',
    22:'lll',
    23:'ddd',
    24:'wf',
    25:'ending',
    26:'castle_courtyard',
    27:'pss',
    28:'cotmc',
    29:'totwc',
    30:'bowser_1',
    31:'wmotr',
    33:'bowser_2',
    34:'bowser_3',
    36:'ttm'
}
#Levelname uses a different castle inside name which is dumb
Num2Name = {6:'castle_inside',**Num2LevelName}

class Area():
    def __init__(self,root,geo,levelRoot,num,scene):
        self.root = root
        self.geo=geo.strip()
        self.num=num
        self.scene=scene
        #Set level root as parent
        Parent(levelRoot,root)
        #set default vars
        root.sm64_obj_type = 'Area Root'
        root.areaIndex=num
    def AddWarp(self,args):
        #set context to the root
        bpy.context.view_layer.objects.active = self.root
        #call fast64s warp node creation operator
        bpy.ops.bone.add_warp_node()
        warp=self.root.warpNodes[0]
        warp.warpID=args[0]
        warp.destNode=args[3]
        level=args[1].strip().replace("LEVEL_",'').lower()
        if level=='castle':
            level='castle_inside'
        if level.isdigit():
            level=Num2Name.get(eval(level))
            if not level:
                level='bob'
        warp.destLevelEnum=level
        warp.destArea=args[2]
        chkpoint=args[-1].strip()
        #Sorry for the hex users here
        if 'WARP_NO_CHECKPOINT' in chkpoint or int(chkpoint.isdigit()*chkpoint+'0')==0:
            warp.warpFlagEnum='WARP_NO_CHECKPOINT'
        else:
            warp.warpFlagEnum='WARP_CHECKPOINT'
    def AddObject(self,args):
        Obj = bpy.data.objects.new('Empty',None)
        self.scene.collection.objects.link(Obj)
        Parent(self.root,Obj)
        Obj.name = "Object {} {}".format(args[8].strip(),args[0].strip())
        Obj.sm64_obj_type= 'Object'
        Obj.sm64_behaviour_enum= 'Custom'
        Obj.sm64_obj_behaviour=args[8].strip()
        Obj.sm64_obj_bparam=args[7]
        Obj.sm64_obj_model=args[0]
        loc=[eval(a.strip())/self.scene.blenderToSM64Scale for a in args[1:4]]
        #rotate to fit sm64s axis
        loc=[loc[0],-loc[2],loc[1]]
        Obj.location=loc
        rot=[math.radians(eval(a.strip())) for a in args[4:7]]
        rot = [rot[0],-rot[2],rot[1]]
        rot=Euler(rot)
        Obj.rotation_euler.rotate(rot)
        #set act mask
        mask=args[-1]
        if type(mask)==str and mask.isdigit():
            mask=eval(mask)
        form='sm64_obj_use_act{}'
        if mask==31:
            for i in range(1,7,1):
                setattr(Obj,form.format(i),True)
        else:
            for i in range(1,7,1):
                if mask&(1<<i):
                    setattr(Obj,form.format(i),True)
                else:
                    setattr(Obj,form.format(i),False)
    
class Level():
    def __init__(self,scr,scene,root):
        self.script=scr
        self.GetScripts()
        self.scene=scene
        self.Areas={}
        self.CurrArea=None
        self.root=root
    def ParseScript(self,entry):
        Start=self.Scripts[entry]
        scale=self.scene.blenderToSM64Scale
        for l in Start:
            args=self.StripArgs(l)
            LsW=l.startswith
            #Find an area
            if LsW("AREA"):
                Root = bpy.data.objects.new('Empty',None)
                self.scene.collection.objects.link(Root)
                Root.name = "{} Area Root {}".format(self.scene.LevelImp.Level,args[0])
                self.Areas[args[0]] = Area(Root,args[1],self.root,int(args[0]),self.scene)
                self.CurrArea=args[0]
                continue
            #End an area
            if LsW("END_AREA"):
                self.CurrArea=None
                continue
            #Jumps are only taken if they're in the script.c file for now
            #continues script
            elif LsW("JUMP_LINK"):
                if self.Scripts.get(args[0]):
                    self.ParseScript(args[0])
                continue
            #ends script
            elif LsW("JUMP"):
                if self.Scripts.get(args[0]):
                    self.ParseScript(entry)
                break
            #final exit of recursion
            elif LsW("EXIT") or l.startswith("RETURN"):
                return
            #Now deal with data cmds rather than flow control ones
            if LsW("WARP_NODE"):
                self.Areas[self.CurrArea].AddWarp(args)
                continue
            if LsW("OBJECT_WITH_ACTS"):
                #convert act mask from ORs of act names to a number
                mask=args[-1].strip()
                if not mask.isdigit():
                    mask=mask.replace("ACT_",'')
                    mask=mask.split('|')
                    #Attempt for safety I guess
                    try:
                        a=0
                        for m in mask:
                            a+=1<<int(m)
                        mask=a
                    except:
                        mask=31
                self.Areas[self.CurrArea].AddObject([*args[:-1],mask])
                continue
            if LsW("OBJECT"):
                #Only difference is act mask, which I set to 31 to mean all acts
                self.Areas[self.CurrArea].AddObject([*args,31])
                continue
            #Don't support these for now
            if LsW("MACRO_OBJECTS"):
                continue
            if LsW("TERRAIN_TYPE"):
                if not args[0].isdigit():
                    self.Areas[self.CurrArea].root.terrainEnum=args[0].strip()
                continue
            if LsW("SHOW_DIALOG"):
                rt=self.Areas[self.CurrArea].root
                rt.showStartDialog=True
                rt.startDialog=args[1].strip()
                continue
            if LsW("TERRAIN"):
                self.Areas[self.CurrArea].terrain = args[0]
                continue
            if LsW("SET_BACKGROUND_MUSIC") or LsW("SET_MENU_MUSIC"):
                rt=self.Areas[self.CurrArea].root
                rt.musicSeqEnum='Custom'
                rt.music_seq=args[-1].strip()
        return self.Areas
    def StripArgs(self,cmd):
        a=cmd.find("(")
        return cmd[a+1:-2].split(',')
    def GetScripts(self):
        #Get a dictionary made up with keys=level script names
        #and values as an array of all the cmds inside.
        self.Scripts={}
        InlineReg="/\*((?!\*/).)*\*/"
        currScr=0
        skip=0
        for l in self.script:
            comment=l.rfind("//")
            #double slash terminates line basically
            if comment:
                l=l[:comment]
            #check for macro
            if '#ifdef' in l:
                skip=EvalMacro(l)
            if '#elif' in l:
                skip=EvalMacro(l)
            if '#else' in l:
                skip=0
            #Now Check for level script starts
            if "LevelScript" in l and not skip:
                b=l.rfind('[]')
                a=l.find('LevelScript')
                var=l[a+11:b].strip()
                self.Scripts[var] = ""
                currScr=var
                continue
            if currScr and not skip:
                #remove inline comments from line
                while(True):
                    m=re.search(InlineReg,l)
                    if not m:
                        break
                    m=m.span()
                    l=l[:m[0]]+l[m[1]:]
                #Check for end of Level Script array
                if "};" in l:
                    currScr=0
                #Add line to dict
                else:
                    self.Scripts[currScr]+=l
        #Now remove newlines from each script, and then split macro ends
        #This makes each member of the array a single macro
        for k,v in self.Scripts.items():
            v=v.replace("\n",'')
            arr=[]
            x=0
            stack=0
            buf=""
            app=0
            while(x<len(v)):
                char=v[x]
                if char=="(":
                    stack+=1
                    app=1
                if char==")":
                    stack-=1
                if app==1 and stack==0:
                    app=0
                    buf+=v[x:x+2] #get the last parenthesis and comma
                    arr.append(buf.strip())
                    x+=2
                    buf=''
                    continue
                buf+=char
                x+=1
            self.Scripts[k]=arr
        return

def ParseAggregat(dat,str,path):
    ldat = dat.readlines()
    cols=[]
    #assume this follows naming convention
    for l in ldat:
        if str in l:
            comment=l.rfind("//")
            #double slash terminates line basically
            if comment:
                l=l[:comment]
            cols.append(l.strip())
    #remove include and quotes inefficiently. Now cols is a list of relative paths
    cols = [c.replace("#include ",'').replace('"','').replace("'",'') for c in cols]
    return [path/c for c in cols]

def FindCollisions(leveldat,lvl,scene,path):
    cols=ParseAggregat(leveldat,'collision.inc.c',path)
    leveldat.close()
    #search for the area terrain in each file
    for k,v in lvl.Areas.items():
        terrain = v.terrain
        found=0
        for c in cols:
            if os.path.isfile(c):
                c=open(c,'r')
                c=c.readlines()
                for i,l in enumerate(c):
                    if terrain in l:
                        #Trim Collision to be just the lines that have the file
                        v.ColFile=c[i:]
                        break
                else:
                    c=None    
                    continue
                break
            else:
                c=None
        if not c:
            raise Exception('Collision {} not found in levels/{}/{}leveldata.c'.format(terrain,scene.LevelImp.Level,scene.LevelImp.Prefix))
        v.ColFile=CleanCollision(v.ColFile)
    return lvl

def CleanCollision(ColFile):
    #Now do the same post processing to macros for potential fuckery that I did to scripts.
    #This means removing comments, dealing with potential multi line macros and making sure each line is one macro
    InlineReg="/\*((?!\*/).)*\*/"
    started=0
    skip=0
    col=''
    for l in ColFile:
        #remove line comment
        comment=l.rfind("//")
        if comment:
            l=l[:comment]
        #check for macro
        if '#ifdef' in l:
            skip=EvalMacro(l)
        if '#elif' in l:
            skip=EvalMacro(l)
        if '#else' in l:
            skip=0
        #Now Check for col start
        if "Collision" in l and not skip:
            started=1
            continue
        if started and not skip:
            #remove inline comments from line
            while(True):
                m=re.search(InlineReg,l)
                if not m:
                    break
                m=m.span()
                l=l[:m[0]]+l[m[1]:]
            #Check for end of Level Script array
            if "};" in l:
                started=0
            #Add line to dict
            else:
                col+=l
    #Now remove newlines from each script, and then split macro ends
    #This makes each member of the array a single macro
    col=col.replace("\n",'')
    arr=[]
    x=0
    stack=0
    buf=""
    app=0
    while(x<len(col)):
        char=col[x]
        if char=="(":
            stack+=1
            app=1
        if char==")":
            stack-=1
        if app==1 and stack==0:
            app=0
            buf+=col[x:x+2] #get the last parenthesis and comma
            arr.append(buf.strip())
            x+=2
            buf=''
            continue
        buf+=char
        x+=1
    return arr

class Collision():
    def __init__(self,col,scale):
        self.col=col
        self.scale=scale
        self.vertices=[]
        #key=type,value=tri data
        self.tris={}
        self.type=None
        self.SpecialObjs=[]
        self.Types=[]
    def GetCollision(self):
        for l in self.col:
            args=self.StripArgs(l)
            #to avoid catching COL_VERTEX_INIT
            if l.startswith('COL_VERTEX') and len(args)==3:
                self.vertices.append([eval(v)/self.scale for v in args])
                continue
            if l.startswith('COL_TRI_INIT'):
                self.type=args[0]
                if not self.tris.get(self.type):
                    self.tris[self.type]=[]
                continue
            if l.startswith('COL_TRI') and len(args)>2:
                a=[eval(a) for a in args]
                self.tris[self.type].append(a)
                continue
            if l.startswith('SPECIAL_OBJECT'):
                self.SpecialObjs.append(args)
        #This will keep track of how to assign mats
        a=0
        for k,v in self.tris.items():
            self.Types.append([a,k])
            a+=len(v)
        self.Types.append([a,0])
    def StripArgs(self,cmd):
        a=cmd.find("(")
        return cmd[a+1:-2].split(',')
    def WriteCollision(self,scene,name,parent):
        mesh = bpy.data.meshes.new(name+' data')
        tris=[]
        for t in self.tris.values():
            #deal with special tris
            if len(t[0])>3:
                t = [a[0:3] for a in t]
            tris.extend(t)
        mesh.from_pydata(self.vertices,[],tris)
        mesh.validate()
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(name+' Mesh',mesh)
        scene.collection.objects.link(obj)
        RotateObj(-90,obj)
        obj.ignore_render=True
        if parent:
            Parent(parent,obj)
        polys=obj.data.polygons
        x=0
        bpy.context.view_layer.objects.active = obj
        max=len(polys)
        for i,p in enumerate(polys):
            a=self.Types[x][0]
            if i>=a:
                bpy.ops.object.create_f3d_mat() #the newest mat should be in slot[-1]
                mat=obj.data.materials[x]
                mat.collision_type_simple = 'Custom'
                mat.collision_custom = self.Types[x][1]
                mat.name="Sm64_Col_Mat_{}".format(self.Types[x][1])
                color=((max-a)/(max),(max+a)/(2*max-a),a/max,1) #Just to give some variety
                mat.f3d_mat.default_light_color = color
                mat.node_tree.nodes["Shade Color"].inputs[2].default_value=color #required because no callback can be applied for script set prop
                x+=1
            p.material_index=x-1


def WriteLevelCollision(lvl,scene):
    for k,v in lvl.Areas.items():
        #dat is a class that holds all the collision files data
        dat=Collision(v.ColFile,scene.blenderToSM64Scale)
        dat.GetCollision()
        name="SM64 {} Area {} Col".format(scene.LevelImp.Level,k)
        dat.WriteCollision(scene,name,v.root)

#This is simply a data storage class
class Mat():
    def __init__(self):
        pass
    def ApplyMatSettings(self,mat,textures,path,layer):
        #make combiner custom
        f3d=mat.f3d_mat #This is kure's custom property class for materials
        f3d.presetName="Custom"
        self.SetCombiner(f3d,layer)
        f3d.draw_layer.sm64 = layer
        #Try to set an imagea
        try:
            i = bpy.data.images.get(self.Timg)
            if not i:
                tex=textures.get(self.Timg)
                if not tex[0].isdigit():
                    tex=tex[0].replace("#include ",'').replace('"','').replace("'",'').replace("inc.c","png")
                fp = path/tex
                i=bpy.data.images.load(filepath=str(fp))
                #Set the image user
                tex0=f3d.tex0
                tex0.tex_set=True
                tex0.tex=i
        except:
            print("Could not find {}".format(self.Timg))
        #Update node values
        override = bpy.context.copy()
        override["material"] = mat
        bpy.ops.material.update_f3d_nodes(override)
    #Very lazy for now
    def SetCombiner(self,f3d,layer):
        if not hasattr(self,'Combiner'):
            layer=eval(layer)
            if layer<=4:
                f3d.combiner1.A = 'TEXEL0'
                f3d.combiner1.A_alpha = '0'
                f3d.combiner1.C = 'SHADE'
                f3d.combiner1.C_alpha = '0'
                f3d.combiner1.D = '0'
                f3d.combiner1.D_alpha = '1'
            if layer==4:
                f3d.combiner1.A = 'TEXEL0'
                f3d.combiner1.A_alpha = 'TEXEL0'
                f3d.combiner1.C = 'SHADE'
                f3d.combiner1.C_alpha = 'SHADE'
                f3d.combiner1.D = '0'
                f3d.combiner1.D_alpha = '0'
            if layer==5:
                f3d.combiner1.A = 'TEXEL0'
                f3d.combiner1.A_alpha = 'TEXEL0'
                f3d.combiner1.C = 'SHADE'
                f3d.combiner1.C_alpha = 'PRIMITIVE'
                f3d.combiner1.D = '0'
                f3d.combiner1.D_alpha = '0'
            if layer>=6:
                f3d.combiner1.A = 'TEXEL0'
                f3d.combiner1.B = 'SHADE'
                f3d.combiner1.A_alpha = '0'
                f3d.combiner1.C = 'TEXEL0_ALPHA'
                f3d.combiner1.C_alpha = '0'
                f3d.combiner1.D = 'SHADE'
                f3d.combiner1.D_alpha = 'ENVIRONMENT'

class F3d():
    def __init__(self,scene):
        self.VB={}
        self.Gfx={}
        self.diff={}
        self.amb={}
        self.Lights={}
        self.Textures={}
        self.scene=scene
    #Textures only contains the texture data found inside the model.inc.c file and the texture.inc.c file
    def GetGenericTextures(self,path):
        for t in ['cave.c','effect.c','fire.c','generic.c','grass.c','inside.c','machine.c','mountain.c','outside.c','sky.c','snow.c','spooky.c','water.c']:
            t = path/'bin'/t
            t=open(t,'r')
            tex=t.readlines()
            #For textures, try u8, and s16 aswell
            self.Textures.update(FormatDat(tex,'Texture',[None,None]))
            self.Textures.update(FormatDat(tex,'u8',[None,None]))
            self.Textures.update(FormatDat(tex,'s16',[None,None]))
            t.close()
    #recursively parse the display list in order to return a bunch of model data
    def GetDataFromModel(self,start):
        DL=self.Gfx.get(start)
        self.VertBuff=[0]*32 #If you're doing some fucky shit with a larger vert buffer it sucks to suck I guess
        if not DL:
            raise Exception("Could not find DL {} in levels/{}/{}leveldata.inc.c".format(start,self.scene.LevelImp.Level,self.scene.LevelImp.Prefix))
        self.Verts=[]
        self.Tris=[]
        self.UVs=[]
        self.VCs=[]
        self.Mats=[]
        self.LastMat=Mat()
        self.ParseDL(DL)
        self.NewMat=0
        self.StartName=start
        return [self.Verts,self.Tris]
    def ParseDL(self,DL):
        #This will be the equivalent of a giant switch case
        x=-1
        while(x<len(DL)):
            #manaual iteration so I can skip certain children efficiently
            x+=1
            l=DL[x]
            LsW=l.startswith
            args=self.StripArgs(l)
            #Deal with control flow first
            if LsW('gsSPEndDisplayList'):
                return
            if LsW('gsSPBranchList'):
                NewDL=self.Gfx.get(args[0].strip())
                if not DL:
                    raise Exception("Could not find DL {} in levels/{}/{}leveldata.inc.c".format(NewDL,self.scene.LevelImp.Level,self.scene.LevelImp.Prefix))
                self.ParseDL(NewDL)
                break
            if LsW('gsSPDisplayList'):
                NewDL=self.Gfx.get(args[0].strip())
                if not DL:
                    raise Exception("Could not find DL {} in levels/{}/{}leveldata.inc.c".format(NewDL,self.scene.LevelImp.Level,self.scene.LevelImp.Prefix))
                self.ParseDL(NewDL)
                continue
            #Vertices
            if LsW('gsSPVertex'):
                VB=self.VB.get(args[0].strip())
                if not VB:
                    print(self.VB)
                    raise Exception("Could not find VB {} in levels/{}/{}leveldata.inc.c".format(args[0],self.scene.LevelImp.Level,self.scene.LevelImp.Prefix))
                Verts=VB[:eval(args[1])] #If you use array indexing here then you deserve to have this not work
                Verts=[self.ParseVert(v) for v in Verts]
                for k,i in enumerate(range(eval(args[2]),eval(args[1]),1)):
                    self.VertBuff[i]=[Verts[k],eval(args[2])]
                #These are all independent data blocks in blender
                self.Verts.extend([v[0] for v in Verts])
                self.UVs.extend([v[1] for v in Verts])
                self.VCs.extend([v[2] for v in Verts])
                self.LastLoad=eval(args[1])
                continue
            #Triangles
            if LsW('gsSP2Triangles'):
                self.MakeNewMat()
                Tri1=self.ParseTri(args[:3])
                Tri2=self.ParseTri(args[4:7])
                self.Tris.append(Tri1)
                self.Tris.append(Tri2)
                continue
            if LsW('gsSP1Triangle'):
                self.MakeNewMat()
                Tri=self.ParseTri(args[:3])
                self.Tris.append(Tri)
                continue
            #materials
            #Mats will be placed sequentially. The first item of the list is the triangle number
            #The second is the material class
            if LsW('gsDPSetTextureImage'):
                self.NewMat=1
                self.LastMat.Timg = args[3].strip()
                self.LastMat.Fmt = args[0].strip()
                self.LastMat.Siz = args[1].strip()
                continue
            if LsW('gsDPSetTile'):
                self.NewMat=1
                self.LastMat.Fmt=args[0].strip()
                self.LastMat.Siz=args[1].strip()
    def MakeNewMat(self):
        if self.NewMat:
            self.NewMat=0
            self.Mats.append([len(self.Tris),self.LastMat])
            self.LastMat=deepcopy(self.LastMat) #for safety
    def ParseVert(self,Vert):
        v=Vert.replace('{','').replace('}','').split(',')
        num=(lambda x: [eval(a) for a in x])
        pos=num(v[:3])
        uv=num(v[4:6])
        vc=num(v[6:10])
        return [pos,uv,vc]
    def ParseTri(self,Tri):
        L=len(self.Verts)
        return [eval(a)+L-self.LastLoad for a in Tri]
    def StripArgs(self,cmd):
        a=cmd.find("(")
        return cmd[a+1:-2].split(',')
    def ApplyDat(self,obj,mesh,layer,path):
        tris=mesh.polygons
        bpy.context.view_layer.objects.active = obj
        ind=-1
        UVmap = obj.data.uv_layers.new(name='UVMap')
        Vcol = obj.data.vertex_colors.new(name='Col')
        Valph = obj.data.vertex_colors.new(name='Alpha')
        self.Mats.append([len(tris)+1,0])
        for i,t in enumerate(tris):
            if i>=self.Mats[ind+1][0]:
                bpy.ops.object.create_f3d_mat() #the newest mat should be in slot[-1]
                ind+=1
                mat=mesh.materials[ind]
                mat.name = "SM64 {} F3D Mat {}".format(self.StartName,ind)
                self.Mats[ind][1].ApplyMatSettings(mat,self.Textures,path,layer)
            t.material_index=ind
            #Get texture size or assume 32, 32 otherwise
            i=mesh.materials[ind].f3d_mat.tex0.tex
            if not i:
                WH=(32,32)
            else:
                WH=i.size
            #Set UV data and Vertex Color Data
            for v,l in zip(t.vertices,t.loop_indices):
                uv=self.UVs[v]
                vcol=self.VCs[v]
                #scale verts. I just copy/pasted this from kirby tbh Idk
                UVmap.data[l].uv = [a*.001*(32/b) if b>0 else a*.001*32 for a,b in zip(uv,WH)]
                Vcol.data[l].color = [a/255 for a in vcol]
        
    
    
def FormatModel(gfx,model,path):
    #For each data type, make an attribute where it cleans the input of the model files
    gfx.VB.update(FormatDat(model,'Vtx',["{","}"]))
    gfx.Gfx.update(FormatDat(model,'Gfx',["(",")"]))
    gfx.diff.update(FormatDat(model,'Light_t',[None,None]))
    gfx.amb.update(FormatDat(model,'Ambient_t',[None,None]))
    gfx.Lights.update(FormatDat(model,'Lights1',[None,None]))
    #For textures, try u8, and s16 aswell
    gfx.Textures.update(FormatDat(model,'Texture',[None,None]))
    gfx.Textures.update(FormatDat(model,'u8',[None,None]))
    gfx.Textures.update(FormatDat(model,'s16',[None,None]))
    return gfx

#Heavily copied from CleanGeo
def FormatDat(model,Type,Chars):
    #Get a dictionary made up with keys=level script names
    #and values as an array of all the cmds inside.
    Models={}
    InlineReg="/\*((?!\*/).)*\*/"
    currScr=0
    skip=0
    for l in model:
        comment=l.rfind("//")
        #double slash terminates line basically
        if comment:
            l=l[:comment]
        #check for macro
        if '#ifdef' in l:
            skip=EvalMacro(l)
        if '#elif' in l:
            skip=EvalMacro(l)
        if '#else' in l:
            skip=0
        #Now Check for level script starts
        if Type in l and '[]' in l and not skip:
            b=l.rfind('[]')
            a=l.find(Type)
            var=l[a+len(Type):b].strip()
            Models[var] = ""
            currScr=var
            continue
        if currScr and not skip:
            #remove inline comments from line
            while(True):
                m=re.search(InlineReg,l)
                if not m:
                    break
                m=m.span()
                l=l[:m[0]]+l[m[1]:]
            #Check for end of Level Script array
            if "};" in l:
                currScr=0
            #Add line to dict
            else:
                Models[currScr]+=l
    #Now remove newlines from each script, and then split macro ends
    #This makes each member of the array a single macro
    for k,v in Models.items():
        v=v.replace("\n",'')
        arr=[]
        x=0
        stack=0
        buf=""
        app=0
        while(x<len(v)):
            char=v[x]
            if char==Chars[0]:
                stack+=1
                app=1
            if char==Chars[1]:
                stack-=1
            if app==1 and stack==0:
                app=0
                buf+=v[x:x+2] #get the last parenthesis and comma
                arr.append(buf.strip())
                x+=2
                buf=''
                continue
            buf+=char
            x+=1
        #for when the control flow characters are nothing
        if buf:
            arr.append(buf)
        Models[k]=arr
    return Models

#I will make these arbitrary later but for now its copy/paste bad code
def CleanGeo(Geo):
    #Get a dictionary made up with keys=level script names
    #and values as an array of all the cmds inside.
    GeoLayouts={}
    InlineReg="/\*((?!\*/).)*\*/"
    currScr=0
    skip=0
    for l in Geo:
        comment=l.rfind("//")
        #double slash terminates line basically
        if comment:
            l=l[:comment]
        #check for macro
        if '#ifdef' in l:
            skip=EvalMacro(l)
        if '#elif' in l:
            skip=EvalMacro(l)
        if '#else' in l:
            skip=0
        #Now Check for level script starts
        if "GeoLayout" in l and not skip:
            b=l.rfind('[]')
            a=l.find('GeoLayout')
            var=l[a+9:b].strip()
            GeoLayouts[var] = ""
            currScr=var
            continue
        if currScr and not skip:
            #remove inline comments from line
            while(True):
                m=re.search(InlineReg,l)
                if not m:
                    break
                m=m.span()
                l=l[:m[0]]+l[m[1]:]
            #Check for end of Level Script array
            if "};" in l:
                currScr=0
            #Add line to dict
            else:
                GeoLayouts[currScr]+=l
    #Now remove newlines from each script, and then split macro ends
    #This makes each member of the array a single macro
    for k,v in GeoLayouts.items():
        v=v.replace("\n",'')
        arr=[]
        x=0
        stack=0
        buf=""
        app=0
        while(x<len(v)):
            char=v[x]
            if char=="(":
                stack+=1
                app=1
            if char==")":
                stack-=1
            if app==1 and stack==0:
                app=0
                buf+=v[x:x+2] #get the last parenthesis and comma
                arr.append(buf.strip())
                x+=2
                buf=''
                continue
            buf+=char
            x+=1
        GeoLayouts[k]=arr
    return GeoLayouts

def FindModels(geo,lvl,scene,path):
    layouts=ParseAggregat(geo,'geo.inc.c',path)
    #Format all geos in geo.c, because geo layouts can branch and reference each other
    GeoLayouts={}
    for l in layouts:
        l=open(l,'r')
        lines=l.readlines()
        GeoLayouts.update(CleanGeo(lines))
    for k,v in lvl.Areas.items():
        GL=v.geo
        rt = v.root
        Geo=GeoLayout(GeoLayouts,rt,scene,"GeoRoot {} {}".format(scene.LevelImp.Level,k),rt)
        Geo.ParseLevelGeosStart(GL)
        v.geo=Geo
        #So the key now is to just have pointers to all the models inside the geo layout class
    return lvl


def FindModelDat(model,scene,path):
    leveldat = open(model,'r')
    models=ParseAggregat(leveldat,'model.inc.c',path)
    leveldat.close()
    leveldat = open(model,'r') #some fuckery where reading lines causes it to have issues
    textures=ParseAggregat(leveldat,'texture.inc.c',path) #Only deal with textures that are actual .pngs
    leveldat.close()
    leveldat = open(model,'r') #some fuckery where reading lines causes it to have issues
    textures.extend(ParseAggregat(leveldat,'textureNew.inc.c',path)) #For RM2C support
    #Get all modeldata in the level
    Models=F3d(scene)
    for m in models:
        md=open(m,'r')
        lines=md.readlines()
        Models=FormatModel(Models,lines,path)
    #Update file to have texture.inc.c textures
    for t in textures:
        t=open(t,'r')
        tex=t.readlines()
        #For textures, try u8, and s16 aswell
        Models.Textures.update(FormatDat(tex,'Texture',[None,None]))
        Models.Textures.update(FormatDat(tex,'u8',[None,None]))
        Models.Textures.update(FormatDat(tex,'s16',[None,None]))
        t.close()
    return Models


class GeoLayout():
    def __init__(self,GeoLayouts,root,scene,name,Aroot):
        self.GL=GeoLayouts
        self.parent=root
        self.models=[]
        self.Children=[]
        self.scene=scene
        self.RenderRange=None
        self.Aroot=Aroot #for properties that can only be written to area
        #make an empty node to act as the root of this geo layout
        E = bpy.data.objects.new(name,None)
        self.root=E
        scene.collection.objects.link(E)
        Parent(root,E)
    def ParseLevelGeosStart(self,start):
        GL=self.GL.get(start)
        if not GL:
            raise Exception("Could not find geo layout {} from levels/{}/{}geo.c".format(v.geo,scene.LevelImp.Level,scene.LevelImp.Prefix))
        self.ParseLevelGeos(GL,0)
    #So I can start where ever for child nodes
    def ParseLevelGeos(self,GL,depth):
        #I won't parse the geo layout perfectly. For now I'll just get models. This is mostly because fast64
        #isn't a bijection to geo layouts, the props are sort of handled all over the place
        x=-1
        while(x<len(GL)):
            #manaual iteration so I can skip certain children efficiently
            x+=1
            l=GL[x]
            LsW=l.startswith
            args=self.StripArgs(l)
            #Jumps are only taken if they're in the script.c file for now
            #continues script
            if LsW("GEO_BRANCH_AND_LINK"):
                NewGL=self.GL.get(args[0].strip())
                if NewGL:
                    self.ParseLevelGeos(NewGL,depth)
                continue
            #continues
            elif LsW("GEO_BRANCH"):
                NewGL=self.GL.get(args[1].strip())
                if NewGL:
                    self.ParseLevelGeos(NewGL,depth)
                if eval(args[0]):
                    continue
                else:
                    break
            #final exit of recursion
            elif LsW("GEO_END") or l.startswith("GEO_RETURN"):
                return
            #on an open node, make a child
            elif LsW("GEO_CLOSE_NODE"):
                if depth:
                    return
            elif LsW("GEO_OPEN_NODE"):
                GeoChild=GeoLayout(self.GL,self.root,self.scene,l,self.Aroot)
                GeoChild.ParseLevelGeos(GL[x+1:],depth+1)
                x=self.SkipChildren(GL,x)
                self.Children.append(GeoChild)
                continue
            #Append to models array. Only check this one for now
            elif LsW("GEO_DISPLAY_LIST"):
                #translation, rotation, layer, model
                self.models.append([(0,0,0),(0,0,0),*args])
                continue
            elif LsW("GEO_SWITCH_CASE"):
                Switch = self.root
                Switch.sm64_obj_type = 'Switch'
                Switch.switchParam=eval(args[0])
                Switch.switchFunc=args[1]
                continue
            #This has to be applied to meshes
            elif LsW("GEO_RENDER_RANGE"):
                self.RenderRange=args
                continue
            #can only apply type to area root
            elif LsW("GEO_CAMERA"):
                self.Aroot.camOption = 'Custom'
                self.Aroot.camType = args[0]
                continue
            #Geo backgrounds is pointless because the only background possible is the one
            #loaded in the level script. This is the only override
            elif LsW("GEO_BACKGROUND_COLOR"):
                self.Aroot.areaOverrideBG=True
                color=eval(args[0])
                A=color&1
                B=(color&0x3E)>1
                G=(color&(0x3E<<5))>>6
                R=(color&(0x3E<<10))>>11
                self.Aroot.areaBGColor=(R/0x1F,G/0x1F,B/0x1F,A)
    def SkipChildren(self,GL,x):
        open=0
        opened=0
        while(x<len(GL)):
            l=GL[x]
            if l.startswith('GEO_OPEN_NODE'):
                opened=1
                open+=1
            if l.startswith('GEO_CLOSE_NODE'):
                open-=1
            if open==0 and opened:
                break
            x+=1
        return x
    def StripArgs(self,cmd):
        a=cmd.find("(")
        return cmd[a+1:-2].split(',')

#Dict converting
Layers={
'LAYER_FORCE':'0',
'LAYER_OPAQUE':'1',
'LAYER_OPAQUE_DECAL':'2',
'LAYER_OPAQUE_INTER':'3',
'LAYER_ALPHA':'4',
'LAYER_TRANSPARENT':'5',
'LAYER_TRANSPARENT_DECAL':'6',
'LAYER_TRANSPARENT_INTER':'7',
}

def ReadGeoLayout(geo,scene,models,path):
    if geo.models:
        rt=geo.root
        #create a mesh for each one
        for m in geo.models:
            mesh = bpy.data.meshes.new(m[3]+' Data')
            [verts,tris] = models.GetDataFromModel(m[3].strip())
            mesh.from_pydata(verts,[],tris)
            mesh.validate()
            mesh.update(calc_edges=True)
            obj = bpy.data.objects.new(m[3]+' Obj',mesh)
            layer=m[2]
            if not layer.isdigit():
                layer=Layers.get(layer)
                if not layer:
                    layer=1
            obj.draw_layer_static=layer
            scene.collection.objects.link(obj)
            Parent(rt,obj)
            RotateObj(-90,obj)
            scale=1/scene.blenderToSM64Scale
            obj.scale=[scale,scale,scale]
            models.ApplyDat(obj,mesh,layer,path)
    if not geo.Children:
        return
    for g in geo.Children:
        ReadGeoLayout(g,scene,models,path)


def WriteLevelModel(lvl,scene,path,modelDat):
    for k,v in lvl.Areas.items():
        #Parse the geolayout class I created earlier to look for models
        ReadGeoLayout(v.geo,scene,modelDat,path)

        #Gonna not use armatures
        
#        Arm=bpy.data.armatures.new("SM64 {} {} Geo".format(scene.LevelImp.Level,k)) #This is the armature data
#        ArmObj=bpy.data.objects.new("Armature",Arm) #This is the armature object
#        scene.collection.objects.link(ArmObj)
        #Now we begin the fuckening
        
    return lvl



def ParseScript(script,scene):
    scr = open(script,'r')
    Root = bpy.data.objects.new('Empty',None)
    scene.collection.objects.link(Root)
    Root.name = "Level Root {}".format(scene.LevelImp.Level)
    Root.sm64_obj_type = 'Level Root'
    #Now parse the script and get data about the level
    #Store data in attribute of a level class then assign later and return class
    scr=scr.readlines()
    lvl = Level(scr,scene,Root)
    entry = scene.LevelImp.Entry.format(scene.LevelImp.Level)
    lvl.ParseScript(entry)
    return lvl

class SM64_OT_Import(Operator):
    bl_label = "Import Level"
    bl_idname = "wm.sm64_import_level"

    def execute(self, context):
        scene = context.scene
        scene.gameEditorMode = 'SM64'
        prefix=scene.LevelImp.Prefix
        path = Path(scene.decompPath)
        level = path/'levels'/scene.LevelImp.Level
        script= level/(prefix+'script.c')
        geo = level/(prefix+'geo.c')
        model = level/(prefix+'leveldata.c')
        ColD = open(model,'r')
        geo=open(geo,'r')
        lvl=ParseScript(script,scene) #returns level class
        lvl=FindCollisions(ColD,lvl,scene,path) #Now Each area has its collision file nicely formatted
        WriteLevelCollision(lvl,scene)
        lvl=FindModels(geo,lvl,scene,path)
        models=FindModelDat(model,scene,path)
        models.GetGenericTextures(path)
        lvl=WriteLevelModel(lvl,scene,path,models)
        return {'FINISHED'}

class LevelImport(PropertyGroup):
    Level: EnumProperty(
        name = "Level",
        description="Choose a level",
        items=[
            ('bbh','bbh',''),
            ('ccm','ccm',''),
            ('hmc','hmc',''),
            ('ssl','ssl',''),
            ('bob','bob',''),
            ('sl','sl',''),
            ('wdw','wdw',''),
            ('jrb','jrb',''),
            ('thi','thi',''),
            ('ttc','ttc',''),
            ('rr','rr',''),
            ('castle_grounds','castle_grounds',''),
            ('castle_inside','castle_inside',''),
            ('bitdw','bitdw',''),
            ('vcutm','vcutm',''),
            ('bitfs','bitfs',''),
            ('sa','sa',''),
            ('bits','bits',''),
            ('lll','lll',''),
            ('ddd','ddd',''),
            ('wf','wf',''),
            ('ending','ending',''),
            ('castle_courtyard','castle_courtyard',''),
            ('pss','pss',''),
            ('cotmc','cotmc',''),
            ('totwc','totwc',''),
            ('bowser_1','bowser_1',''),
            ('wmotr','wmotr',''),
            ('bowser_2','bowser_2',''),
            ('bowser_3','bowser_3',''),
            ('ttm','ttm','')
        ]
        )
    Prefix: StringProperty(
        name = "Prefix",
        description="Prefix before expected aggregator files like script.c, leveldata.c and geo.c",
        default=""
    )
    Entry: StringProperty(
        name = "Entrypoint",
        description="The name of the level script entry variable",
        default="level_{}_entry"
    )
    Version: EnumProperty(
        name='Version',
        description="Version of the game for any ifdef macros",
        items=[
        ('VERSION_US','VERSION_US',''),
        ('VERSION_JP','VERSION_JP',''),
        ('VERSION_EU','VERSION_EU',''),
        ('VERSION_SH','VERSION_SH',''),
        ]
    )
    Target: StringProperty(
        name = "Target",
        description="The platform target for any #ifdefs in code",
        default="TARGET_N64"
    )

class ImportPanel(Panel):
    bl_label = "SM64 Level Importer"
    bl_idname = "sm64_level_importer"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "SM64 Level Import"
    bl_context = "objectmode"   

    @classmethod
    def poll(self,context):
        return context.scene is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        LevelImp = scene.LevelImp
        layout.prop(LevelImp, "Level")
        layout.prop(LevelImp,"Entry")
        layout.prop(LevelImp,"Prefix")
        layout.prop(LevelImp,"Version")
        layout.prop(LevelImp,"Target")
        layout.operator("wm.sm64_import_level")

classes = (
    LevelImport,
    SM64_OT_Import,
    ImportPanel
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    bpy.types.Scene.LevelImp = PointerProperty(type=LevelImport)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.my_tool

if __name__ == "__main__":
    register()