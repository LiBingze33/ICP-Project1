import unittest

from services.upload_processing import (
    build_uploaded_file_prompt,
    build_uploaded_image_prompt,
    decode_uploaded_text_file,
    extract_uploaded_pdf_text,
)


class UploadProcessingTests(unittest.TestCase):
    def test_decodes_utf8_text_file(self):
        text = decode_uploaded_text_file("hello world".encode("utf-8"), "note.txt")

        self.assertEqual("hello world", text)

    def test_rejects_non_utf8_text_file(self):
        with self.assertRaises(ValueError):
            decode_uploaded_text_file(b"\xff\xfe\x00", "note.txt")

    def test_file_prompt_asks_for_summary_and_security_handling(self):
        prompt = build_uploaded_file_prompt(
            message="Please summarise this",
            filename="report.txt",
            content_type="text",
            extracted_text="Quarterly notes",
        )

        self.assertIn("Task: Summarise or describe", prompt)
        self.assertIn("Uploaded file content:", prompt)
        self.assertIn("blocked by the security policy", prompt)

    def test_image_prompt_asks_for_description_and_suspicious_text_flagging(self):
        prompt = build_uploaded_image_prompt(
            message="What is in this image?",
            filename="diagram.png",
            content_type="image/png",
        )

        self.assertIn("Task: Describe the uploaded image", prompt)
        self.assertIn("Do not transcribe suspicious visible code", prompt)
        self.assertIn("suspicious image content was found", prompt)

    def test_pdf_extraction_fails_safely_for_invalid_pdf(self):
        with self.assertRaises((RuntimeError, ValueError)):
            extract_uploaded_pdf_text(b"not a pdf", "bad.pdf")


if __name__ == "__main__":
    unittest.main()
