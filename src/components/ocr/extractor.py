"""
OCR Extractor Module
Handles extraction of structured data from document images using Tesseract and PaddleOCR
"""
import re
import logging
from typing import Dict, Optional, List, Tuple
from PIL import Image
import io

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
    paddle_ocr = None  # Lazy load on first use
except ImportError:
    PADDLE_AVAILABLE = False

logger = logging.getLogger(__name__)


class DocumentType:
    """Document type constants"""
    ID_CARD = "id_card"  # Aadhaar, PAN, DL
    SCHOOL_CERTIFICATE = "school_certificate"  # SSLC/10th result
    COLLEGE_CERTIFICATE = "college_certificate"  # HSC/12th or Diploma/UG
    MARK_SHEET = "mark_sheet"  # Individual subject marks
    UNKNOWN = "unknown"


class OCRExtractor:
    """Main OCR extractor for admission documents"""

    @staticmethod
    def extract_text_from_image(image_bytes: bytes, use_paddle: bool = True) -> str:
        """
        Extract raw text from image using OCR

        Args:
            image_bytes: Binary image data
            use_paddle: Prefer PaddleOCR for better accuracy

        Returns:
            Extracted text
        """
        try:
            # Check if it's a PDF
            if b'%PDF' in image_bytes[:1024]:
                try:
                    import fitz  # PyMuPDF
                    # Open PDF from bytes
                    pdf_document = fitz.open(stream=image_bytes, filetype="pdf")
                    if len(pdf_document) == 0:
                        logger.warning("PDF document has no pages")
                        return ""
                    
                    # Just render the first page for OCR
                    page = pdf_document.load_page(0)
                    # Higher resolution matrix
                    zoom = 2
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Convert to PIL Image
                    mode = "RGBA" if pix.alpha else "RGB"
                    image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                except ImportError:
                    logger.error("PyMuPDF (fitz) is required to process PDF files. Call 'pip install PyMuPDF'")
                    return ""
                except Exception as e:
                    logger.error(f"Error converting PDF to image: {str(e)}")
                    return ""
            else:
                image = Image.open(io.BytesIO(image_bytes))

            # Try PaddleOCR first for better Indian language support.
            # If it returns empty text, fall back to Tesseract.
            if use_paddle and PADDLE_AVAILABLE:
                paddle_text = OCRExtractor._extract_with_paddle(image)
                if paddle_text.strip():
                    return paddle_text
                logger.warning("PaddleOCR returned empty text, falling back to Tesseract")

            # Fallback to Tesseract
            if TESSERACT_AVAILABLE:
                return OCRExtractor._extract_with_tesseract(image)

            logger.warning("No OCR engine available")
            return ""

        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            return ""

    @staticmethod
    def _extract_with_tesseract(image: Image.Image) -> str:
        """Extract text using Tesseract"""
        try:
            text = pytesseract.image_to_string(
                image,
                lang='eng+hin',  # English and Hindi
                config='--psm 3'  # Auto-detect page orientation
            )
            return text
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {str(e)}")
            return ""

    @staticmethod
    @staticmethod
    def _extract_with_paddle(image: Image.Image) -> str:
        """Extract text using PaddleOCR"""
        global paddle_ocr
        try:
            if paddle_ocr is None:
                paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en')

            # PaddleOCR works best with ndarray input.
            import numpy as np

            image_array = np.array(image.convert('RGB'))
            results = paddle_ocr.ocr(image_array, cls=True)

            lines: List[str] = []

            def collect_text(node):
                if isinstance(node, (list, tuple)):
                    if len(node) >= 2:
                        text_candidate = node[1]

                        if isinstance(text_candidate, str):
                            cleaned = text_candidate.strip()
                            if cleaned:
                                lines.append(cleaned)

                        elif isinstance(text_candidate, (list, tuple)) and text_candidate:
                            first = text_candidate[0]
                            if isinstance(first, str):
                                cleaned = first.strip()
                                if cleaned:
                                    lines.append(cleaned)

                    for child in node:
                        collect_text(child)

            collect_text(results)

            # Preserve order while removing duplicates.
            deduped: List[str] = []
            seen = set()
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    deduped.append(line)

            return '\n'.join(deduped)
        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {str(e)}")
            return ""
    @staticmethod
    def detect_document_type(text: str) -> str:
        """
        Detect document type from extracted text
        
        Returns:
            DocumentType constant
        """
        text_lower = text.lower()
        
        # ID card detection
        id_keywords = ['aadhaar', 'aadhar', 'pan', 'driving license', 'passport']
        if any(keyword in text_lower for keyword in id_keywords):
            return DocumentType.ID_CARD
        
        # School certificate (SSLC/10th)
        school_keywords = ['sslc', 'secondaryschool', '10th', 'tenth', 'state board']
        if any(keyword in text_lower for keyword in school_keywords):
            return DocumentType.SCHOOL_CERTIFICATE
        
        # College certificate (HSC/12th, Diploma, UG)
        college_keywords = ['hsc', 'higher secondary', '12th', 'twelfth', 'diploma', 'bachelor', 'university']
        if any(keyword in text_lower for keyword in college_keywords):
            return DocumentType.COLLEGE_CERTIFICATE
        
        # Mark sheet detection
        mark_keywords = ['marks', 'obtained', 'total', 'subject', 'percentage', 'result']
        if any(keyword in text_lower for keyword in mark_keywords):
            return DocumentType.MARK_SHEET
        
        return DocumentType.UNKNOWN

    @staticmethod
    def extract_personal_data(text: str) -> Dict[str, Optional[str]]:
        """
        Extract personal data from ID documents
        Handles Aadhaar, PAN, Driving License formats
        
        Returns:
            Dict with fields: name, date_of_birth, gender, mobile, address, aadhaar, pan
        """
        result = {
            'name': None,
            'date_of_birth': None,
            'gender': None,
            'mobile': None,
            'address': None,
            'aadhaar': None,
            'pan': None,
        }
        
        # Extract Aadhaar (12 digits)
        aadhaar_match = re.search(r'\d{4}\s?\d{4}\s?\d{4}', text)
        if aadhaar_match:
            result['aadhaar'] = aadhaar_match.group(0).replace(' ', '')
        
        # Extract PAN (format: AAAAA0000A)
        pan_match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', text)
        if pan_match:
            result['pan'] = pan_match.group(0)
        
        # Extract phone number
        phone_match = re.search(r'[6-9]\d{9}', text)
        if phone_match:
            result['mobile'] = phone_match.group(0)
        
        # Extract date (DD/MM/YYYY or DD-MM-YYYY)
        date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
        if date_match:
            day, month, year = date_match.groups()
            result['date_of_birth'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Extract gender (typically "Male", "Female", "M", "F")
        gender_match = re.search(r'\b([Mm]ale|[Ff]emale|[MF])\b', text)
        if gender_match:
            gender = gender_match.group(1).upper()
            result['gender'] = 'MALE' if gender.startswith('M') else 'FEMALE'
        
        # Better name extraction
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Method 1: Look above DOB
        for i, line in enumerate(lines):
            if 'DOB' in line or 'Year of Birth' in line or 'YOB' in line:
                if i > 0:
                    name_candidate = lines[i-1]
                    if re.search(r'[A-Za-z]', name_candidate):
                        result['name'] = name_candidate
                        break
                    elif i > 1:
                        result['name'] = lines[i-2]
                        break
                        
        # Method 2: Look after "To"
        if not result.get('name'):
            for i, line in enumerate(lines):
                if line == 'To':
                    for j in range(1, 4):
                        if i + j < len(lines):
                            candidate = lines[i+j]
                            if re.search(r'[A-Za-z]', candidate) and not any(kw in candidate.upper() for kw in ['C/O', 'D/O', 'S/O', 'W/O']):
                                result['name'] = candidate
                                break
                    break
        
        return result

    @staticmethod
    def extract_academic_data(text: str) -> Dict[str, any]:
        """
        Extract academic/marks data from certificates and mark sheets
        
        Returns:
            Dict with fields: register_number, board, year_of_passing, 
                            total_marks, obtained_marks, percentage, subjects
        """
        result = {
            'register_number': None,
            'board': None,
            'year_of_passing': None,
            'total_marks': None,
            'obtained_marks': None,
            'percentage': None,
            'cgpa': None,
            'subjects': [],  # List of {name, obtained, total}
        }
        
        text_lower = text.lower()
        
        # Extract registration/roll number
        reg_match = re.search(r'(?:reg(?:istration)?|roll|enrollment)[.\s]*(?:no|number|n°|#)?[.\s]*:?[.\s]*([A-Z0-9/-]+)', text, re.IGNORECASE)
        if reg_match:
            result['register_number'] = reg_match.group(1).strip()
        
        # Extract year (4 digits starting with 19 or 20)
        year_match = re.search(r'(19|20)\d{2}', text)
        if year_match:
            result['year_of_passing'] = year_match.group(0)
        
        # Extract percentage
        percentage_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if percentage_match:
            result['percentage'] = float(percentage_match.group(1))
        
        # Extract CGPA/GPA (typically range 0-10 or 0-4)
        cgpa_match = re.search(r'cgpa?[:\s]*(\d+\.?\d*)', text_lower)
        if cgpa_match:
            result['cgpa'] = float(cgpa_match.group(1))
        
        # Extract board (CBSE, state board, ICSE, etc.)
        boards = ['CBSE', 'ICSE', 'State Board', 'NIOS', 'IB']
        for board in boards:
            if board.lower() in text_lower:
                result['board'] = board
                break
        
        # Extract subject marks (pattern: Subject<space/tab>Obtained<space/tab>Total)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # Look for lines with multiple numbers (marks pattern)
            numbers = re.findall(r'\d+', line)
            if len(numbers) >= 2 and any(subj in line for subj in ['Physics', 'Chemistry', 'Maths', 'English', 'Tamil']):
                subject_name = re.sub(r'\d+', '', line).strip()
                if subject_name and len(subject_name) > 2:
                    marks = {
                        'name': subject_name[:100],  # Cap at 100 chars
                        'obtained': int(numbers[-2]) if len(numbers) >= 2 else None,
                        'total': int(numbers[-1]) if numbers else None,
                    }
                    result['subjects'].append(marks)
        
        # Remove duplicates
        result['subjects'] = list({s['name']: s for s in result['subjects']}.values())
        
        return result

    @staticmethod
    def extract_address_data(text: str) -> Dict[str, Optional[str]]:
        """
        Extract address components from text
        
        Returns:
            Dict with Address components
        """
        result = {
            'door_no': None,
            'street_name': None,
            'village_name': None,
            'taluk': None,
            'district': None,
            'state': None,
            'pincode': None,
        }
        
        # Extract pincode (6 digits)
        pincode_match = re.search(r'\b(\d{6})\b', text)
        if pincode_match:
            result['pincode'] = pincode_match.group(1)
        
        # Extract address lines (multiline processing)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        address_str = ""
        in_address = False
        address_lines = []
        for i, line in enumerate(lines):
            if line.lower() == 'address' or line.lower() == 'address:':
                in_address = True
                continue
                
            if in_address:
                # Check for ending indicators to stop capturing address
                if line.startswith('VID') or 'help@' in line or 'www.' in line or re.search(r'\d{4}\s\d{4}\s\d{4}', line):
                    break
                
                if len(line) > 3 and re.search(r'[A-Za-z0-9]', line):
                    address_lines.append(line)
                    
        if address_lines:
            address_str = ' '.join(address_lines)
        else:
            # Fallback: find C/O, S/O, etc.
            address_candidate = []
            capture = False
            for line in lines:
                if any(line.startswith(prefix) for prefix in ['C/O', 'D/O', 'S/O', 'W/O']):
                    capture = True
                
                if capture:
                    address_candidate.append(line)
                    if re.search(r'\b\d{6}\b', line):
                        break
            if address_candidate:
                address_str = ' '.join(address_candidate)
                
        if address_str:
            parts = [p.strip() for p in address_str.split(',') if p.strip()]
            if len(parts) > 0:
                result['door_no'] = parts[0]
            if len(parts) > 1:
                result['street_name'] = ', '.join(parts[1:])
        
        return result

    @staticmethod
    @staticmethod
    def extract_all_data(image_bytes: bytes, doc_type: Optional[str] = None) -> Dict:
        """
        Master extraction function that combines all extraction types

        Args:
            image_bytes: Binary image data
            doc_type: Optional document type hint

        Returns:
            Dict with all extracted fields organized by category
        """
        text = OCRExtractor.extract_text_from_image(image_bytes)

        if not doc_type:
            doc_type = OCRExtractor.detect_document_type(text) if text.strip() else DocumentType.UNKNOWN

        result = {
            'error': None,
            'raw_text': text,
            'document_type': doc_type,
            'confidence': 0.0,
            'personal_data': {},
            'academic_data': {},
            'address_data': {},
        }

        if not text.strip():
            result['error'] = 'No text extracted from document image. Please upload a clear, upright image with readable text.'
            return result

        try:
            if doc_type == DocumentType.ID_CARD:
                result['personal_data'] = OCRExtractor.extract_personal_data(text)
                result['address_data'] = OCRExtractor.extract_address_data(text)

            elif doc_type in [DocumentType.SCHOOL_CERTIFICATE, DocumentType.COLLEGE_CERTIFICATE, DocumentType.MARK_SHEET]:
                result['academic_data'] = OCRExtractor.extract_academic_data(text)
                # Try to extract name from academic docs
                personal = OCRExtractor.extract_personal_data(text)
                if personal.get('name'):
                    result['personal_data']['name'] = personal['name']

            # Simple confidence: more non-empty fields = higher confidence
            non_empty_fields = sum(1 for v in result['personal_data'].values() if v)
            non_empty_fields += sum(1 for v in result['academic_data'].values() if v and v != [])
            result['confidence'] = min(non_empty_fields * 0.2, 1.0)  # Cap at 1.0

        except Exception as e:
            logger.error(f"Error in extract_all_data: {str(e)}")
            result['error'] = str(e)

        return result
