const PowerPoint = require("activeXPowerPoint");
const app = new PowerPoint.Application();
app.Visible = true;
const presentation = app.Presentations.Add();

function addSlide(title, content) {
    const slideIndex = presentation.Slides.Count + 1;
    const slide = presentation.Slides.Add(slideIndex, 1);
    slide.Shapes.Title.TextFrame.TextRange.Text = title;
    slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = content;
}

// Title Slide
let slide = presentation.Slides.Add(1, 1);
slide.Shapes.Title.TextFrame.TextRange.Text = "Advanced Issues in Email Technology";
slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = "A Presentation on Email Challenges & Solutions";

// Content Slides
addSlide("1. Email Spoofing & Phishing Attacks", "- Attackers forge headers to mimic legitimate senders\n- Leads to scams and malware\n- Solution: SPF, DKIM, DMARC");
addSlide("2. Spam & Email Filtering Challenges", "- False positives and false negatives\n- Solution: AI-powered spam filters");
addSlide("3. Email Encryption & Privacy Concerns", "- Emails can be intercepted\n- Solution: PGP, S/MIME, TLS encryption");
addSlide("4. Email Deliverability Issues", "- Emails may not reach recipients\n- Solution: Maintain IP reputation, use verified domains");
addSlide("5. Large Email Attachments & Bandwidth Usage", "- Many email servers restrict attachment sizes\n- Solution: Use cloud storage links");
addSlide("6. Email Tracking & Privacy Violations", "- Marketers track email activity\n- Solution: Block tracking pixels");
addSlide("7. AI-Powered Email Threats", "- AI-generated phishing emails\n- Solution: AI-based anomaly detection");
addSlide("8. Cross-Platform Compatibility Issues", "- Email rendering differs across clients\n- Solution: Use responsive templates and testing tools");

// Save and Close Options (Uncomment if needed)
// presentation.SaveAs("C:\\Users\\YourUsername\\Desktop\\Email_Issues.pptx");
// app.Quit();
