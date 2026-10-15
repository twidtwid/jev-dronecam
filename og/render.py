import asyncio
from playwright.async_api import async_playwright
from PIL import Image
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1200,"height":630},device_scale_factor=2)
        await pg.goto("file://"+__import__("os").path.abspath("og.html")); await pg.wait_for_selector("body[data-ready]"); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(400)
        await pg.screenshot(path="og@2x.png"); await b.close()
    Image.open("og@2x.png").convert("RGB").resize((1200,630),Image.LANCZOS).save("og.jpg",quality=88,optimize=True,progressive=True)
asyncio.run(main())
