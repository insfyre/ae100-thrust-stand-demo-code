Last updated 11/20/2025 by Eugene
Sean Lee, Eugene Lim, Ahmed Khan



# AE 100 NI USB6009 Force Logger v1.1

WINDOWS ONLY--You will have to rebuild the binary/executable yourself to run on Linux. In addition, you will need to download the appropriate NI-DAQmx drivers from the National Instruments website. (if the drivers in the zip file are out of date, https://www.ni.com/en/support/downloads/drivers/download.ni-daq-mx.html#577117 should work)



### How to install

1. If needed, unzip folder.
2. Disable Fast Startup in control panel -> hardware settings -> power options -> choose what the power buttons do -> uncheck "Turn on Fast Startup". Having this setting on seems to interfere with NI driver installation. With Fast Startup disabled, startup should take ~30 s longer with SSD, longer if you have a hard drive. (but now there should be greater system stability after a restart)
3. Run ni-daqmx\_25.5\_online.exe. National Instruments driver installation. Deselect all additional items except certificates. This step takes a while (~1 hr). It will ask you to restart your computer at end of driver installation.
   a) You can deselect certificates, but that will result in several popup prompts that you will have to click through (unsure how that works)
4. Run NI\_USB6009\_ForceLogger.exe. This is the actual data logging software.
   a) If Windows Defender pops up, go to More info -> Run anyway. This is a byproduct of the packaging process (since the exe contains the entire Python interpreter and all of the program's dependent packages, when it unpacks it looks like a virus).
   b) Wait ~1 min for startup. Once the program starts, you should see a green blinking light on the 6009 DAQ box (if not, once you hit start you should see that light)
5. Hit these buttons in the following order: \[Start], \[Tare]. ONLY press \[TARE] once.
6. Set appropriate force ranges \["Y Min" and "Y Max"], \[Apply Y-Range].
7. Hit \[Record] to record data to CSV. Once you hit the record button, depending on how long the filename is the \[Apply Y-Range] button will go out of range. It should come back once you hit \[Stop] button.
8. Hit \[Stop] to stop collecting data/reset the Tare settings. This also stops recording to the current CSV.
   a) From here, you can start a new recording, or make changes to the settings. It should make a new CSV if you hit \[START] again.
9. When done/you want to reload the program, simply close the window.
   a) If needed, go to task manager and kill the process (NI\_USB6009\_ForceLogger.exe). Bug should be fixed \[2025-11-20] where closing the GUI window would not kill the program.



# Developmental notes



Software works by interfacing with the separate NI-DAQmx software running in the background. Quick diagram:



Force --> load cell --> USB6009 DAQ --> NI-DAQmx on computer --> NI\_USB6009\_ForceLogger.exe



NI\_USB6009\_ForceLogger.exe is a single file created by PyInstaller package from Python. This contains:

* Entire Python interpreter
* Entirety of packages: matplotlib, nidaqmx, tkinter, along with all those dependencies (including numpy)

  * All the packages included in the exe can be found in the environments.yml file extracted from Conda (that you can reimport into Miniconda/Anaconda)

* Actual program, thrust\_stand.py

As you can see, this is a waste of space, resulting in a ~190 MB file. To save space, I tried packaging the program as a C/C++ executable via Nuitka (spent a lot of time on this!), but that didn't work; apparently ..\\numpy\\core\\\_multiarray\_umath.pyd consistently failed to import when the executable was unpackaging (maybe Nuitka changed the name when it was unpacking?).

Fixed, just need to also copy package "nitypes" metadata in addition to "nidaqmx"



* Most program settings should be accessible from the GUI



Recompile if:

* You are tired of changing the settings and need to set new defaults

  * Note: We only tested changing the Calibration (N/V), Y Min/Y Max, and X Min/X Max settings; unsure if changing the other settings via the GUI will work

* You want to add more functionality/nicer GUI
* Zoom function for graph
* To combine sampling rate ("Fs" samples/second divided by samples/read)
* The program isn't working at a fundamental level and you need to fix the bug



If you are changing hardware (load cell/DAQ)

* Voltage range *probably* shouldn't change
* Device name and Analog Input (AI) channel names will probably change, run the first few cells of the Jupyter notebook to check
* As long as the max sampling rate is higher than the default, you should be fine



Sean's environment: Conda environment but using pypi to install, Python version 3.11



Changelog:

* 11/01/2025: Set default scaling factor based on measured weight of calculator, added
* 11/15/2025: Added "kill on window close" functionality (sys.exit())
* 11/20/2025: Fixed kill on close functionality to only happen on window close, not when stop button is pressed. Added free pan feature from Matplotlib
