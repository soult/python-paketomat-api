import io
import itertools
import subprocess

try:
    from PIL import Image
except:
    PIL_AVAILABLE = False
else:
    PIL_AVAILABLE = True

def convert_to_png(pdf):
    proc = subprocess.Popen(
        ["gs", "-q", "-sDEVICE=pngalpha", "-sOutputFile=%stdout%", "-r203", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    return proc.communicate(pdf)[0]

def format_label(png):
    if not PIL_AVAILABLE:
        return png

    img = Image.open(io.BytesIO(png))

    def map_pixel(pixel):
        if pixel[3] == 0:
            return (255, 255, 255)

        intensity = 0.299 * pixel[0] + 0.587  * pixel[1] + 0.114 * pixel[2]
        if intensity < 127 and pixel[3] > 127:
            return (0, 0, 0)
        else:
            return (255, 255, 255)

    img2 = Image.new("RGB", img.size)
    img2.putdata(list(map(map_pixel, img.getdata())))

    target = Image.new("RGB", (800, 1200), (255, 255, 255))
    target.paste(img2, (0, 0, img2.size[0], img2.size[1]))

    buf = io.BytesIO()
    target.save(buf, "PNG")
    return buf.getvalue()
