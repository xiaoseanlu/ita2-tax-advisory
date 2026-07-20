"""
Financial Document API smoke test (POST /v2/documents, GET children).

**Cookie-first (recommended):** set ``SESSION_COOKIES`` (+ optional ``FINANCIALDOC_API_KEY``) like
``tax-advisory-toolkit`` ``test_iam_extraction.py``. When cookies are present, this script does **not**
send IAM app-secret headers so you avoid DES/7216-gated behavior.

**IAM (optional):** set ``IAM_APP_SECRET``, ``IAM_TOKEN``, ``IAM_USER_ID`` only when **no** ``SESSION_COOKIES``,
or force with ``TEST_IAM_EXTRACTION_FORCE_IAM=1``.

Shared env with ``iam_pdf_extraction.py``: ``FINANCIALDOC_BASE_URL``, ``INTUIT_OFFERING_ID``,
``EXPERT_E2E_IAM_TAX_YEAR`` / ``DEFAULT_TAX_YEAR``, ``EXPERT_E2E_IAM_IS7216``.

For a **scenario-ready summary** after a good run, use::

  python3 iam_pdf_extraction.py your.pdf --output-dir ./out

and read ``out/user_inputs_summary.txt`` and ``out/tax_input_summary.txt``, or call
``extract_1040_from_pdf_for_scenario()`` from Python.
"""

import asyncio
import httpx
import json
import os
import sys
import argparse
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from email import message_from_bytes
from email.policy import default


def document_type_to_simple_name(
    doc_type: str, existing_names: Optional[set] = None
) -> str:
    """
    Convert API documentType to a simple filename base (no UUID).
    E.g. tax::Form1040ScheduleC -> ScheduleC, tax::Form1040Composite -> Form1040.
    When existing_names is provided, disambiguates duplicates (ScheduleC_2, etc.).
    """
    if not doc_type or doc_type == "unknown":
        base = "Unknown"
    else:
        part = doc_type.split("::")[-1] if "::" in doc_type else doc_type
        if part == "Form1040Composite":
            base = "Form1040"
        elif part == "Form1040":
            base = "Form1040"
        elif part.startswith("Form1040"):
            base = part[len("Form1040") :] or "Form1040"
        else:
            base = part
    if existing_names is not None:
        name = base
        counter = 1
        while name in existing_names:
            counter += 1
            name = f"{base}_{counter}"
        existing_names.add(name)
        return name
    return base


# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(env_path)
except ImportError:
    print("⚠️  python-dotenv not installed. Using system environment variables.")

try:
    from iam_pdf_extraction import (
        _upload_common_is7216,
        cookies_header_to_dict,
        financialdoc_upload_tax_year,
    )
except ImportError:
    def cookies_header_to_dict(raw: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in (raw or "").split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
        return out

    def financialdoc_upload_tax_year(pdf_path: Optional[Path] = None) -> int:
        raw = (os.getenv("EXPERT_E2E_IAM_TAX_YEAR") or os.getenv("DEFAULT_TAX_YEAR") or "2024").strip()
        try:
            return int(raw)
        except ValueError:
            return 2024

    def _upload_common_is7216() -> bool:
        return (os.getenv("EXPERT_E2E_IAM_IS7216") or "1").strip().lower() not in ("0", "false", "no")


class IAMDocumentsAPIClient:
    """Client matching the exact curl command format with IAM authentication or cookies"""

    def __init__(
        self, 
        base_url: str,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
        cookies: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        intuit_offering_id: str = "Intuit.incometax.prep.directtaxui",
    ):
        """
        Initialize the API client
        
        Args:
            base_url: Base URL for the API
            app_id: IAM application ID (optional if using cookies)
            app_secret: IAM application secret (optional if using cookies)
            token: IAM token (optional if using cookies)
            user_id: User ID (optional if using cookies)
            cookies: Session cookies string (alternative to IAM)
            api_key: API key (alternative to IAM)
            timeout: Request timeout in seconds
            intuit_offering_id: POST ``intuit_offeringid`` (override with INTUIT_OFFERING_ID in .env)
        """
        self.base_url = base_url.rstrip('/')
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.user_id = user_id
        self.cookies = cookies
        self.api_key = api_key
        self.timeout = timeout
        self.intuit_offering_id = intuit_offering_id

        self.cookies_dict = None
        if cookies:
            d = cookies_header_to_dict(cookies)
            self.cookies_dict = d if d else None

    def _get_iam_auth_header(self) -> Optional[str]:
        """Build IAM authentication header"""
        if all([self.app_id, self.app_secret, self.token, self.user_id]):
            return (
                f"Intuit_IAM_Authentication "
                f"intuit_appid={self.app_id}, "
                f"intuit_app_secret={self.app_secret}, "
                f"intuit_token={self.token}, "
                f"intuit_userid={self.user_id}, "
                f"intuit_token_type=IAM-Ticket"
            )
        elif self.api_key:
            return f"Intuit_APIKey intuit_apikey={self.api_key}"
        return None

    async def create_document(
        self,
        pdf_file_path: str,
        document_json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Upload document - exactly matching the curl POST command
        
        Args:
            pdf_file_path: Path to the PDF file
            document_json_data: Document metadata as dict
            
        Returns:
            Response from the API
        """
        url = f"{self.base_url}/v2/documents"
        
        # Headers matching curl exactly
        headers = {
            'Accept': 'application/json;version=3.0.0',
            'channel': 'localFile',
            'intuit_offeringid': self.intuit_offering_id,
            'intuit_tid': f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-browser"
        }
        
        # Add authorization if available
        auth_header = self._get_iam_auth_header()
        if auth_header:
            headers['Authorization'] = auth_header
        
        # Read PDF file
        pdf_path = Path(pdf_file_path)
        if not pdf_path.exists():
            return {
                'success': False,
                'error': f'PDF file not found: {pdf_file_path}',
                'status_code': None
            }
        
        with open(pdf_path, 'rb') as f:
            pdf_content = f.read()
        
        # DEBUG: Print request details
        print("\n" + "=" * 80)
        print("🔍 DEBUG: POST /v2/documents REQUEST")
        print("=" * 80)
        print(f"\n📍 URL: {url}")
        
        print(f"\n📨 Headers:")
        for key, value in headers.items():
            if 'secret' in key.lower() or 'token' in key.lower():
                print(f"   {key}: [REDACTED]")
            elif key == 'Authorization':
                auth_type = "IAM" if "IAM_Authentication" in value else "API Key"
                print(f"   {key}: {auth_type} [credentials redacted]")
            else:
                print(f"   {key}: {value}")
        
        print(f"\n🍪 Cookies: {'Yes (' + str(len(self.cookies_dict)) + ' cookies)' if self.cookies_dict else 'None'}")
        
        print(f"\n📦 Multipart Form Data:")
        print(f"   Part 1: 'document' (JSON)")
        print(f"      {json.dumps(document_json_data, indent=6)}")
        print(f"   Part 2: 'file' (PDF)")
        print(f"      Filename: {pdf_path.name}")
        print(f"      Size: {len(pdf_content):,} bytes")
        print("=" * 80 + "\n")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Prepare multipart form data - matching curl format
                files = {
                    'document': ('blob', json.dumps(document_json_data), 'application/json'),
                    'file': (pdf_path.name, pdf_content, 'application/pdf')
                }
                
                response = await client.post(
                    url,
                    files=files,
                    headers=headers,
                    cookies=self.cookies_dict
                )
                
                # DEBUG: Print response
                print("\n" + "=" * 80)
                print("📥 DEBUG: POST /v2/documents RESPONSE")
                print("=" * 80)
                print(f"\n✓ Status Code: {response.status_code}")
                print(f"✓ Response Time: {response.elapsed.total_seconds() * 1000:.0f}ms")
                
                print(f"\n📨 Response Headers:")
                for key, value in response.headers.items():
                    print(f"   {key}: {value}")
                
                print(f"\n📦 Response Body Preview (first 1000 chars):")
                response_preview = response.text[:1000] if hasattr(response, 'text') else str(response.content[:1000])
                print(f"   {response_preview}")
                if len(response.content) > 1000:
                    print(f"   ... ({len(response.content):,} total bytes)")
                print("=" * 80 + "\n")
                
                response.raise_for_status()
                
                # Parse response
                response_data = None
                semantic_data = None
                content_type = response.headers.get('content-type', '')
                
                if 'multipart/form-data' in content_type:
                    # Parse multipart response
                    try:
                        msg_content = f"Content-Type: {content_type}\r\n\r\n".encode() + response.content
                        msg = message_from_bytes(msg_content, policy=default)
                        
                        for part in msg.iter_parts():
                            content_disposition = part.get('Content-Disposition', '')
                            if 'name="semanticData"' in content_disposition:
                                semantic_data_text = part.get_content()
                                try:
                                    semantic_data = json.loads(semantic_data_text)
                                except json.JSONDecodeError:
                                    semantic_data = semantic_data_text
                        
                        response_data = {'semanticData': semantic_data}
                    except Exception as e:
                        print(f"⚠️  Multipart parsing error: {e}")
                        response_data = {'raw': response.text[:1000]}
                elif response.content:
                    try:
                        response_data = response.json()
                    except json.JSONDecodeError:
                        response_data = {'raw': response.text}
                
                # Extract document ID
                document_id = None
                location = response.headers.get('location', '')
                if location and '/documents/' in location:
                    document_id = location.split('/documents/')[-1]
                
                if semantic_data:
                    print("\n" + "=" * 80)
                    print("📊 DEBUG: SEMANTIC DATA EXTRACTED")
                    print("=" * 80)
                    for schema_name, schema_data in semantic_data.items():
                        if isinstance(schema_data, dict):
                            print(f"\n✓ Schema: {schema_name}")
                            print(f"   Fields: {len(schema_data)}")
                            print(f"   Sample fields: {list(schema_data.keys())[:10]}")
                    print("=" * 80 + "\n")
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'data': response_data,
                    'semantic_data': semantic_data,
                    'document_id': document_id,
                    'headers': dict(response.headers),
                    'elapsed_ms': response.elapsed.total_seconds() * 1000
                }
                
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text if e.response.text else 'No error details'
                
                # Extract document ID even on error
                document_id = None
                location = e.response.headers.get('location', '')
                if location and '/documents/' in location:
                    document_id = location.split('/documents/')[-1]
                
                return {
                    'success': False,
                    'error': f'HTTP {e.response.status_code}: {error_detail}',
                    'status_code': e.response.status_code,
                    'document_id': document_id,
                    'response_text': error_detail,
                    'response_headers': dict(e.response.headers)
                }
            except httpx.RequestError as e:
                return {
                    'success': False,
                    'error': f'Request error: {str(e)}',
                    'status_code': None
                }

    async def get_document(
        self,
        document_id: str,
        output_basename: Optional[str] = None,
        save_response: bool = True,
    ) -> Dict[str, Any]:
        """
        Get document - exactly matching the curl GET command

        Args:
            document_id: The document ID
            output_basename: If set, save response to {output_basename}.json (no UUID).
            save_response: If False, do not save response to file (caller will save with simple name).

        Returns:
            Response from the API
        """
        url = f"{self.base_url}/v2/documents/{document_id}"
        
        # Headers matching curl exactly
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/xml'
        }
        
        # Add authorization if available
        auth_header = self._get_iam_auth_header()
        if auth_header:
            headers['Authorization'] = auth_header
        
        # DEBUG: Print request
        print("\n" + "=" * 80)
        print("🔍 DEBUG: GET /v2/documents/{id} REQUEST")
        print("=" * 80)
        print(f"\n📍 URL: {url}")
        print(f"📍 Document ID: {document_id}")
        
        print(f"\n📨 Headers:")
        for key, value in headers.items():
            if key == 'Authorization':
                auth_type = "IAM" if "IAM_Authentication" in value else "API Key"
                print(f"   {key}: {auth_type} [credentials redacted]")
            else:
                print(f"   {key}: {value}")
        
        print(f"\n🍪 Cookies: {'Yes (' + str(len(self.cookies_dict)) + ' cookies)' if self.cookies_dict else 'None'}")
        print("=" * 80 + "\n")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers, cookies=self.cookies_dict)
                
                # DEBUG: Print response
                print("\n" + "=" * 80)
                print("📥 DEBUG: GET /v2/documents/{id} RESPONSE")
                print("=" * 80)
                print(f"\n✓ Status Code: {response.status_code}")
                print(f"✓ Response Time: {response.elapsed.total_seconds() * 1000:.0f}ms")
                
                print(f"\n📨 Response Headers:")
                for key, value in response.headers.items():
                    print(f"   {key}: {value}")
                
                print(f"\n📦 Response Body Preview (first 1000 chars):")
                response_preview = response.text[:1000]
                print(f"   {response_preview}")
                if len(response.content) > 1000:
                    print(f"   ... ({len(response.content):,} total bytes)")
                
                # Save complete response to file (simple name when output_basename provided)
                if save_response:
                    response_file = Path(__file__).parent / (
                        f"{output_basename}.json" if output_basename
                        else f"get_response_{document_id}.json"
                    )
                try:
                    response_json = response.json()
                    if save_response:
                        with open(response_file, 'w', encoding='utf-8') as f:
                            json.dump(response_json, f, indent=2, ensure_ascii=False)
                        print(f"\n💾 Complete GET response saved to: {response_file.name}")
                    # Parse and check key fields
                    sys_attrs = response_json.get('systemAttributes', {})
                    print(f"\n🔑 Key Composite Fields:")
                    print(f"   classificationDetails: {sys_attrs.get('classificationDetails', 'N/A')}")
                    print(f"   children: {sys_attrs.get('children', 'N/A')}")
                    print(f"   entities: {sys_attrs.get('entities', 'N/A')}")
                    print(f"   extractor: {sys_attrs.get('extractor', 'N/A')}")
                    print(f"   dataExtractionStatus: {sys_attrs.get('dataExtractionStatus', 'N/A')}")
                except Exception as e:
                    print(f"\n⚠️  Could not parse response: {e}")
                    if save_response:
                        response_file = Path(__file__).parent / (
                            f"{output_basename}.json" if output_basename
                            else f"get_response_{document_id}.json"
                        )
                        with open(response_file.with_suffix('.txt'), 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f"💾 Raw response saved to: {response_file.with_suffix('.txt').name}")
                
                print("=" * 80 + "\n")
                
                response.raise_for_status()
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'data': response.json() if response.content else None,
                    'elapsed_ms': response.elapsed.total_seconds() * 1000
                }
                
            except httpx.HTTPStatusError as e:
                return {
                    'success': False,
                    'error': f'HTTP {e.response.status_code}: {e.response.text}',
                    'status_code': e.response.status_code
                }
            except httpx.RequestError as e:
                return {
                    'success': False,
                    'error': f'Request error: {str(e)}',
                    'status_code': None
                }

    async def delete_document(
        self,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Delete a document
        
        Args:
            document_id: The document ID to delete
            
        Returns:
            Response from the API
        """
        # First GET the document to get Last-Modified header
        get_url = f"{self.base_url}/v2/documents/{document_id}"
        get_headers = {
            'Accept': 'application/json'
        }
        
        auth_header = self._get_iam_auth_header()
        if auth_header:
            get_headers['Authorization'] = auth_header
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Get Last-Modified timestamp
                get_response = await client.get(get_url, headers=get_headers, cookies=self.cookies_dict)
                last_modified = get_response.headers.get('Last-Modified')
                
                if not last_modified:
                    # Use current time if Last-Modified not available
                    from email.utils import formatdate
                    last_modified = formatdate(timeval=None, localtime=False, usegmt=True)
                
                # Now delete with If-Unmodified-Since header
                delete_url = f"{self.base_url}/v2/documents/{document_id}"
                delete_headers = {
                    'Accept': 'application/json',
                    'If-Unmodified-Since': last_modified
                }
                
                if auth_header:
                    delete_headers['Authorization'] = auth_header
                
                print(f"\n🗑️  Deleting document: {document_id}")
                
                response = await client.delete(delete_url, headers=delete_headers, cookies=self.cookies_dict)
                response.raise_for_status()
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'message': f'Document {document_id} deleted successfully'
                }
                
            except httpx.HTTPStatusError as e:
                return {
                    'success': False,
                    'error': f'HTTP {e.response.status_code}: {e.response.text}',
                    'status_code': e.response.status_code
                }
            except httpx.RequestError as e:
                return {
                    'success': False,
                    'error': f'Request error: {str(e)}',
                    'status_code': None
                }


async def main(pdf_filename: str = "Adams, Abigail.pdf", delete_on_server: bool = True):
    """
    Main test workflow

    Args:
        pdf_filename: Name of the PDF file to extract (default: "Adams, Abigail.pdf")
        delete_on_server: If True (default), delete uploaded documents from the server after retrieval. If False, leave them on the server.
    """
    
    # Load configuration from .env
    BASE_URL = os.getenv(
        'FINANCIALDOC_BASE_URL',
        'https://financialdocument-e2e.platform.intuit.com'
    )
    
    IAM_APP_ID = os.getenv('IAM_APP_ID', 'Intuit.fdp.extraction.desnextgen')
    IAM_APP_SECRET = os.getenv('IAM_APP_SECRET')
    IAM_TOKEN = os.getenv('IAM_TOKEN')
    IAM_USER_ID = os.getenv('IAM_USER_ID')

    SESSION_COOKIES = os.getenv('SESSION_COOKIES')
    API_KEY = os.getenv('FINANCIALDOC_API_KEY')

    use_cookies = bool(SESSION_COOKIES and str(SESSION_COOKIES).strip())
    force_iam = os.getenv("TEST_IAM_EXTRACTION_FORCE_IAM", "").lower() in ("1", "true", "yes")
    iam_ready = all([IAM_APP_SECRET, IAM_TOKEN, IAM_USER_ID])
    # Browser session wins: avoids DES IAM + 7216 constraints when both are in .env.
    use_iam = iam_ready and (not use_cookies or force_iam)
    use_api_key = bool(API_KEY and str(API_KEY).strip())

    if not (use_iam or use_cookies or use_api_key):
        print("❌ Error: No authentication credentials found in .env file")
        print("\n📝 Recommended — browser session (same as toolkit):")
        print("   SESSION_COOKIES")
        print("   FINANCIALDOC_API_KEY  (often required alongside cookies in e2e)")
        print("\n📝 Optional — IAM app ticket (only if no cookies, or set TEST_IAM_EXTRACTION_FORCE_IAM=1):")
        print("   IAM_APP_ID (defaults to Intuit.fdp.extraction.desnextgen)")
        print("   IAM_APP_SECRET, IAM_TOKEN, IAM_USER_ID")
        return

    if use_iam:
        print("🔐 Authentication: IAM (app secret + ticket)")
        print(f"🔑 IAM App ID: {IAM_APP_ID}")
        print(f"🔑 IAM User ID: {IAM_USER_ID}")
        print(f"🔑 IAM Token: {IAM_TOKEN[:20]}..." if IAM_TOKEN else "❌ Missing")
        if use_cookies and force_iam:
            print("⚠️  TEST_IAM_EXTRACTION_FORCE_IAM=1: IAM header will be sent; cookies still attached.")
    elif use_cookies and use_api_key:
        print("🔐 Authentication: SESSION_COOKIES + FINANCIALDOC_API_KEY (browser / toolkit parity)")
        print(f"🔑 API Key: {API_KEY[:20]}...")
        print(f"🍪 Cookies: {len(SESSION_COOKIES)} chars")
    elif use_api_key:
        print("🔐 Authentication: FINANCIALDOC_API_KEY only")
        print(f"🔑 API Key: {API_KEY[:20]}...")
    else:
        print("🔐 Authentication: SESSION_COOKIES only")
        print(f"🍪 Cookies: {len(SESSION_COOKIES)} chars")
    
    offering = os.getenv("INTUIT_OFFERING_ID", "Intuit.incometax.prep.directtaxui")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📋 intuit_offeringid: {offering}\n")

    client = IAMDocumentsAPIClient(
        base_url=BASE_URL,
        app_id=IAM_APP_ID if use_iam else None,
        app_secret=IAM_APP_SECRET if use_iam else None,
        token=IAM_TOKEN if use_iam else None,
        user_id=IAM_USER_ID if use_iam else None,
        cookies=SESSION_COOKIES if use_cookies else None,
        api_key=API_KEY if use_api_key else None,
        intuit_offering_id=offering,
    )
    
    print("=" * 70)
    print("Financial Document extraction test")
    print("=" * 70)
    
    # Step 1: Upload document
    pdf_path = Path(__file__).parent / pdf_filename
    if not pdf_path.exists():
        print(f"\n❌ PDF not found: {pdf_path}")
        print(f"   Looking in: {Path(__file__).parent.absolute()}")
        return
    
    print(f"\n[1] Uploading document: {pdf_path.name}")
    print(f"    File size: {pdf_path.stat().st_size:,} bytes")
    
    document_json = {
        "commonAttributes": {
            "name": pdf_path.name,
            "documentType": "tax::Form1040Composite",
            "taxYear": financialdoc_upload_tax_year(pdf_path),
            "is7216": _upload_common_is7216(),
            "ttlDuration": "2d",
            "payloadVersion": "3.0.0",
            "documentChannel": "upload",
            "channelType": "localFile",
            "deviceType": "desktopWeb"
        }
    }
    
    upload_result = await client.create_document(
        pdf_file_path=str(pdf_path),
        document_json_data=document_json
    )
    
    if not upload_result['success']:
        print(f"\n❌ Upload failed: {upload_result.get('error')}")
        return
    
    print(f"\n✅ Upload successful!")
    print(f"   Status Code: {upload_result['status_code']}")
    
    document_id = upload_result.get('document_id')
    if document_id:
        print(f"   Document ID: {document_id}")
        
        # Wait for document processing (longer wait for composite extraction)
        print(f"\n⏳ Waiting 60 seconds for document processing and composite extraction...")
        await asyncio.sleep(60)
        
        # Step 2: Get document details (saved as Form1040.json)
        print(f"\n[2] Retrieving document: {document_id}")
        
        get_result = await client.get_document(
            document_id, output_basename="Form1040"
        )
        
        if get_result['success']:
            print(f"\n✅ Document retrieved successfully!")
            
            # Check for semantic data (saved as Form1040_semantic.json)
            doc_data = get_result['data']
            semantic_data = doc_data.get('semanticData')
            if semantic_data:
                print(f"\n📊 Semantic data found!")
                for schema_name in semantic_data.keys():
                    print(f"   - {schema_name}")
                semantic_file = Path(__file__).parent / "Form1040_semantic.json"
                with open(semantic_file, 'w', encoding='utf-8') as f:
                    json.dump(semantic_data, f, indent=2, ensure_ascii=False)
                print(f"💾 Semantic data saved to: {semantic_file.name}")
            
            # Check for child documents (schedules) - save as ScheduleA.json, ScheduleB.json, etc.
            sys_attrs = doc_data.get('systemAttributes', {})
            children = sys_attrs.get('children', [])
            child_ids_to_delete = []
            used_child_names: set = set()
            
            if children and len(children) > 0:
                print(f"\n🎯 Found {len(children)} child document(s) - likely individual schedules!")
                print(f"   Retrieving each child document...\n")
                
                for i, child in enumerate(children, 1):
                    # Children can be either strings (document IDs) or objects
                    if isinstance(child, str):
                        child_id = child
                        child_type = 'unknown'
                    else:
                        child_id = child.get('id') or child.get('documentId')
                        child_type = child.get('documentType', 'unknown')
                    
                    if child_id:
                        print(f"   [{i}/{len(children)}] Retrieving child: (ID: {child_id})")
                        
                        # Track for cleanup
                        child_ids_to_delete.append(child_id)
                        
                        # Small delay between requests
                        if i > 1:
                            await asyncio.sleep(0.5)
                        
                        # Get child document (do not save inside get_document; we save with simple name)
                        child_result = await client.get_document(
                            child_id, save_response=False
                        )
                        
                        if child_result['success']:
                            # Get document type from response
                            child_doc_type = child_result['data'].get('commonAttributes', {}).get('documentType', 'unknown')
                            if child_doc_type == 'unknown':
                                child_doc_type = child_result['data'].get('systemAttributes', {}).get('documentType', 'unknown')
                            
                            # Simple name: ScheduleA.json, ScheduleB.json, etc. (no UUIDs)
                            simple_name = document_type_to_simple_name(
                                child_doc_type, used_child_names
                            )
                            child_file = Path(__file__).parent / f"{simple_name}.json"
                            with open(child_file, 'w', encoding='utf-8') as f:
                                json.dump(child_result['data'], f, indent=2, ensure_ascii=False)
                            print(f"       ✅ Type: {child_doc_type}")
                            print(f"       💾 Saved to: {child_file.name}")
                            
                            # Check for semantic data in child
                            child_semantic = child_result['data'].get('semanticData')
                            if child_semantic:
                                print(f"       📊 Semantic data: {list(child_semantic.keys())}")
                        else:
                            print(f"       ❌ Failed to retrieve child: {child_result.get('error')}")
                    else:
                        print(f"   [{i}/{len(children)}] ⚠️  Child has no ID, skipping")
                
                print(f"\n✅ Retrieved all {len(children)} child documents")
            else:
                print(f"\n⚠️  No child documents found (children array is empty)")
                print(f"   This means no individual schedules were extracted")
            
            # Cleanup: Delete all documents (unless --no-delete)
            if delete_on_server:
                print(f"\n🧹 Cleanup: Deleting all created documents...")

                # Delete child documents first
                if child_ids_to_delete:
                    print(f"\n   Deleting {len(child_ids_to_delete)} child document(s)...")
                    for i, child_id in enumerate(child_ids_to_delete, 1):
                        delete_result = await client.delete_document(child_id)
                        if delete_result['success']:
                            print(f"   [{i}/{len(child_ids_to_delete)}] ✅ Child deleted: {child_id}")
                        else:
                            print(f"   [{i}/{len(child_ids_to_delete)}] ⚠️  Child delete failed: {delete_result.get('error')}")
                        await asyncio.sleep(0.3)  # Small delay between deletes

                # Delete parent document
                print(f"\n   Deleting parent document: {document_id}")
                delete_result = await client.delete_document(document_id)
                if delete_result['success']:
                    print(f"   ✅ Parent document deleted successfully")
                else:
                    print(f"   ⚠️  Parent delete failed: {delete_result.get('error')}")

                print(f"\n✅ Cleanup complete!")
            else:
                print(f"\n📌 Skipping cleanup (--no-delete): documents left on server.")
                print(f"   Parent: {document_id}")
                if child_ids_to_delete:
                    print(f"   Children: {len(child_ids_to_delete)} document(s)")

            print(f"   Note: All extracted data has been saved to local files")
        else:
            print(f"\n❌ Get document failed: {get_result.get('error')}")
    else:
        print(f"\n⚠️  No document ID returned")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Extract tax data from a PDF via Financial Document API (cookies + API key recommended)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 test_iam_extraction.py "Adams, Abigail.pdf"
  python3 test_iam_extraction.py "John Anderson TY24.pdf"
  python3 test_iam_extraction.py --no-delete  # Leave documents on server
  python3 test_iam_extraction.py  # Uses default: "Adams, Abigail.pdf"
        '''
    )
    parser.add_argument(
        'pdf_filename',
        nargs='?',
        default='Adams, Abigail.pdf',
        help='Name of the PDF file to extract (default: "Adams, Abigail.pdf")'
    )
    parser.add_argument(
        '--no-delete',
        action='store_true',
        help='Do not delete documents on the server after retrieval (leave them on the server)'
    )
    args = parser.parse_args()
    asyncio.run(main(args.pdf_filename, delete_on_server=not args.no_delete))
