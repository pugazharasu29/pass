from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

# Create a new PowerPoint presentation
prs = Presentation()

# Set slide layout (0 = title slide)
slide_layout = prs.slide_layouts[0]
slide = prs.slides.add_slide(slide_layout)

# Set title and subtitle
title = slide.shapes.title
subtitle = slide.placeholders[1]

title.text = "ICT MATERIAL"
subtitle.text = "Sample Theme-Based Slide"

# Apply design theme: background color and font style
# Background color - light blue-ish tone to match typical ICT themed designs
background = slide.background
fill = background.fill
fill.solid()
fill.fore_color.rgb = RGBColor(224, 242, 255)  # light blue background

# Format title
title.text_frame.paragraphs[0].font.size = Pt(44)
title.text_frame.paragraphs[0].font.bold = True
title.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)  # deep blue

# Format subtitle
subtitle.text_frame.paragraphs[0].font.size = Pt(24)
subtitle.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 76, 153)  # medium blue
subtitle.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

# Add a content slide to show layout
content_slide_layout = prs.slide_layouts[1]
content_slide = prs.slides.add_slide(content_slide_layout)
content_title = content_slide.shapes.title
content_body = content_slide.placeholders[1]

content_title.text = "Introduction to ICT"
content_body.text = (
    "• Definition of ICT\n"
    "• Importance in modern education\n"
    "• Tools and Applications\n"
    "• Examples: Smart Boards, E-learning Platforms"
)

# Apply same background
fill = content_slide.background.fill
fill.solid()
fill.fore_color.rgb = RGBColor(224, 242, 255)

# Format content
content_title.text_frame.paragraphs[0].font.size = Pt(36)
content_title.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)

content_body.text_frame.paragraphs[0].font.size = Pt(20)
content_body.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 0, 102)

# Save the presentation
pptx_path = "/mnt/data/ICT_Theme_Template.pptx"
prs.save(pptx_path)

pptx_path
