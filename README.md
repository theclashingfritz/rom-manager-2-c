# Rom Manger 2 C

## Intro

Convert sm64 levels made with rom manager or SM64 Editor (not guaranteed to work with all versions) to sm64 decomp compliant C files.

------------------------------------------------------------------

## Dependencies

bistring, capstone, pypng, PIL, ESRGAN (only for ai upscaling for PC port *Currently Testing*)

### Installation

* pip install bitstring
* pip install capstone
* pip install pypng
* pip install pillow

<b> You must use <a href="https://github.com/jesusyoshi54/sm64ex-alo">this (SM64ex-alo)</a> repository for RM2C and set RM2C in the makefile to 1</b>

#### ESRGAN
Currently testing, installation method coming after optimal fork and model are found.

------------------------------------------------------------------

## Usage

place rom in root, run RM2C.py with the following arguments:

RM2C.py, rom="romname", editor=False, levels=[] , actors=[], Append=[(rom,areaoffset,editor),...] WaterOnly=0 ObjectOnly=0 MusicOnly=0 MusicExtend=0 Text=0 Misc=0 Textures=0 Inherit=0 Upscale=0 Title=0

 - Arguments with equals sign are shown in default state, do not put commas between args. All Arguments use python typing, this means you can generate lists or strings using defualt python functions.
 - Levels accept any list argument or only the string 'all'.
 - Actors will accept either a list of groups, a string for a group (see decomp group folders e.g. common0, group1 etc.) the string 'all' for all models, or the string 'new' for only models without a known label, or 'old' for only known original models.
 - Append is for when you want to combine multiple roms. The appended roms will act as if they are an extra area in the original rom, that is they will only export area specific data such as models, objects and music.
 - You must have at least one level to export actors because the script needs to read the model load cmds to find pointers to data.
 - The "Only" options are to only export certain things either to deal with specific updates or updates to RM2C itself. Only use one at a time. An only option will not maintain other data. Do not use Append with MusicOnly, it will have no effect.
 - Use ObjectOnly to export object hacks. If you are using a ToadsTool hack, set Misc=0 or it will hang.
 - MusicExtend is for when you want to add in your custom music on top of the original tracks. Set it to the amount you want to offset your tracks by (0x23 for vanilla). This is only useful when combined with append so the tracks don't overwrite each other.
 - Textures will export the equivalent of the /textures/ folder in decomp.
 - Inherit is a file management arg for when dealing with multiple roms. Normal behavior is to clear level and actor folder each time, inherit prevents this.
 - Title exports the title screen. This will also be exported if levels='all'
 - Upscale is an option to use ESRGAN ai upscaling to increase texture size. The upscaled textures will generate #ifdefs in each model file for non N64 targeting to compile them instead of the original textures. This feature is not currently implemented.

### Example Inputs


1. All models in BoB for editor rom
	* python RM2C.py rom="ASA.z64" editor=1 levels=[9] actors='all'

2. Export all Levels in a RM rom
	* python RM2C.py rom="baserom.z64" levels='all'

3. Export all BoB in a RM rom with a second area from another rom
	* python RM2C.py rom="baserom.z64" levels='all' Append=[('rom2.z64',1,True)]

4. Export text
	*python RM2C.py rom='sm74.z64' Text=1
	
4. Export title screen of one hack while keeping original data
	*python RM2C.py rom='SR1.z64' Title=1 Inerit=1


### NOTE! if you are on unix bash requires you to escape certain characters.
For this module, these are quotes and paranthesis. Add in a escape before each.

* python3 RM2C.py rom=\'sm74.z64\' levels=[9] Append=[\(\'sm74EE.z64\',1,1\)] editor=1

### Expected results
Should extract all levels, scripts, and assets from the levels specified by arguments.

## Usage in Decomp
Drag and drop all exported folders into the root of your decomp repository.
You must manage scripts of individual levels so that custom objects/unknown objects
are properly commented or included in the repo. 

 * For music, delete the original sequences and drop in the extracted ones. Then merge (manually at this moment) the sequences.json with the original sequences.json. For convenience when working with multiple hacks, filenames include the romname, this should not cause any conflicts.
 

**NOTE** sequence numbers must be in numerical order.

***NOT GUARANTEED TO COMPILE DIRECTLY AFTER EXTRACTION***

### Necessary Manual Changes

1. Levels with fog made in editor need their setcombines changed.
	* Change the 2nd cycle value to "0, 0, 0, COMBINED, 0, 0, 0, COMBINED"
	* The cmd prompt will print out warnings whenever fog is encountered. Use that to look at the levels with fog.

2. Appended roms may use different object banks which must be manually handled to prevent crashes.


## Successful results
Ultra Mario Course 1 ported from sm64 editor to SM64EX pc port:

<img src="Extra Resources/UltraMarioPC.png">

Speed Star Adventure Course 1 ported from Rom Manager to SM64 decomp:

<img src="Extra Resources/SSAEmu.png">

## Planned Future Features

* MOP detection/exporting (need to add MOP to base repo)

* Behavior Script Extraction

* Code disassembly and attempted auto decompiling (Far off future)


## Curret issues

* Memory bloat because original data is still included

* End cake picture does export

* Editor Display Lists not auto fixed for fog

* custom objects do not export with labels (plan to have custom map support)

## Image Upscaling

With porting to PC automatically a possiblity, so is the addition of auto upscaling textures for higher quality gameplay. Using ESRGAN and various models I have tested what the best models are for AI upscaling.

<img src="Extra Resources/ESRGAN Comparison.png">