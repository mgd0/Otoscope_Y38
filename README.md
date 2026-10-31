# Otoscope_Y38
Allows use of certain cheap Chinese wireless (WiFi, "Y38" type) Otoscopes on your computer without using their associated, possibly spyware/malware app. Specifically, this takes the place of the AIR-LOOK app. Check out its horrific reviews.

FYI, there's a great looking "Otoscope" app available for Android 10+, but I don't have such a device. Try it if you do!

After some initial WiFi/network investigation, and an attempt to use VLC, I started asking ChattyG for help. Yeah...whatever.

I eventually coaxed it into producing a Python program that reads the scope's video and makes it viewable in a web browser window! This should be usable on any platform. But, you'll need to run it from the command line, then open a browser to:
http://127.0.0.1:8080

For MacOS, I also got it to create a shell script, which can be converted to a clickable application using Automator. You'll find this, the raw script, and the Python program here.

It works great, at a frame rate of maybe 5-10 fps...way better than the 2 fps mentioned in some reviews! Though still a fair latency.

Of course, you need to set your WiFi to the Otoscope's: AIR-ES-...

Hmm, the .app worked the first time, but not so much on my 2nd run. But it did work when run in Automator. Hmm. I've done as much as I plan to with this...

Michael Dunn

