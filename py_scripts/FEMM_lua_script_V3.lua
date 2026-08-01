-- FEMM Lua script V2 01/02/18
-- Will produce a .bmp image of simulation in zoomed region.
-- Rotor torque (weighted stress tensor) estimated for objects in group 1 and printed to console. 
-- Rotor will be rotated n number of steps around point 0,0 over desired rotation range.  

showconsole()
clearconsole()
mydir="./" -- directory that lua script is placed in
open(mydir .. "N5065 Motor.fem") -- name of file that script will run on
mi_saveas(mydir .. "temp.fem")
mi_seteditmode("group")
step=800 -- number of steps to solve where angle resolution = rotation / step
rotation=(360/7) * 2 -- range that rototr will be rotated over
for n=0,step do
    mi_analyze(1) -- 0 = fkern progres window, 1 = hides fkern progres window
    mi_loadsolution()
    if (n == 0) then -- removed for n > 0 to save time
        mo_resize(1200,1000) -- set output window size (width,height)
        mo_zoom(-35,-35,35,35) -- window zoom box size (x1,y1,x2,y2)
    end
    mo_showcontourplot(19,-0.005,0.005,real) --19 contour lines, -0.01 to 0.1
    mo_showdensityplot(1,0,2.1,0,"bmag") --colour flux density plot, 0 to 2.1T
    filename = n..".bmp"
    mo_savebitmap(filename)
    mo_hidedensityplot() -- hidden to speed up subsequent steps 
    mo_hidecontourplot() -- hidden to speed up subsequent steps 
    mo_groupselectblock(1)
    fz=mo_blockintegral(22)
    angle=(rotation/(step-1))
    print(angle*n,fz)
    if (n<step) then
        mi_selectgroup(1)
        mi_moverotate(0,0,angle)
    end
end
mo_close()
mi_close()