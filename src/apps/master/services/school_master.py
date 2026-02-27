"""
School Master Service - handles school list CRUD and CSV/Excel bulk upload
"""
import io
import logging
from uuid import UUID
from typing import Optional

import pandas as pd
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, UploadFile

from common.models.master.admission_masters import SchoolMaster, SchoolListUpload

logger = logging.getLogger(__name__)


class SchoolMasterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_schools(
        self,
        search: Optional[str] = None,
        block: Optional[str] = None,
        district: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ):
        """Get paginated list of schools with optional filters."""
        stmt = select(SchoolMaster).where(
            SchoolMaster.is_active == True,
            SchoolMaster.deleted_at.is_(None),
        )
        if search:
            stmt = stmt.where(SchoolMaster.name.ilike(f"%{search}%"))
        if block:
            stmt = stmt.where(SchoolMaster.block == block)
        if district:
            stmt = stmt.where(SchoolMaster.district == district)

        stmt = stmt.order_by(SchoolMaster.name).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_schools_dropdown(self, block: Optional[str] = None):
        """Simple list for dropdown — returns id, name, block only."""
        stmt = select(SchoolMaster).where(
            SchoolMaster.is_active == True,
            SchoolMaster.deleted_at.is_(None),
        )
        if block:
            stmt = stmt.where(SchoolMaster.block == block)
        stmt = stmt.order_by(SchoolMaster.name)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_blocks(self):
        """Get distinct school blocks for dropdown filter."""
        stmt = (
            select(SchoolMaster.block)
            .where(
                SchoolMaster.is_active == True,
                SchoolMaster.deleted_at.is_(None),
                SchoolMaster.block.isnot(None),
            )
            .distinct()
            .order_by(SchoolMaster.block)
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def create_school(self, data):
        """Create a single school entry."""
        school = SchoolMaster(
            name=data.name,
            block=data.block,
            district=data.district,
            state=data.state or "Tamil Nadu",
        )
        self.db.add(school)
        await self.db.commit()
        await self.db.refresh(school)
        return school

    async def update_school(self, school_id: UUID, data):
        """Update a school entry."""
        update_data = data.dict(exclude_unset=True)
        update_data.pop("id", None)
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")

        result = await self.db.execute(
            update(SchoolMaster)
            .where(SchoolMaster.id == school_id, SchoolMaster.deleted_at.is_(None))
            .values(**update_data)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="School not found")
        await self.db.commit()

        stmt = select(SchoolMaster).where(SchoolMaster.id == school_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def delete_school(self, school_id: UUID):
        """Soft delete a school entry."""
        result = await self.db.execute(
            update(SchoolMaster)
            .where(SchoolMaster.id == school_id, SchoolMaster.deleted_at.is_(None))
            .values(deleted_at=func.now(), is_active=False)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="School not found")
        await self.db.commit()
        return {"message": "School deleted"}

    async def bulk_upload_schools(self, file: UploadFile):
        """
        Parse a CSV, Excel, or PDF file and bulk-insert school records.
        
        Expected for CSV/Excel columns: 
        - name (or school_name) - required
        - block (or block_name)
        - district
        - school_address
        - pincode
        - state (optional, defaults to Tamil Nadu)
        
        Expected for PDF:
        - S NO, DISTRICT, BLOCK NAME, SCHOOL NAME, SCHOOL ADDRESS, PINCODE
        """
        filename = file.filename or ""
        content = await file.read()
        
        logger.info(f"Uploading file: {filename}, size: {len(content)} bytes")

        if not content:
            logger.error(f"File {filename} is empty")
            raise HTTPException(
                status_code=400,
                detail="File is empty",
            )

        errors = []
        df = None
        try:
            if filename.endswith(".csv"):
                logger.info(f"Parsing CSV file: {filename}")
                df = pd.read_csv(io.BytesIO(content))
                logger.info(f"CSV parsed: {len(df)} rows, columns: {list(df.columns)}")
                if df.empty:
                    raise HTTPException(status_code=400, detail="CSV file is empty")
            elif filename.endswith((".xlsx", ".xls")):
                logger.info(f"Parsing Excel file: {filename}")
                # Read all rows to find the actual header row
                all_sheets = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
                logger.info(f"Raw Excel data: {len(all_sheets)} rows")
                
                # Find the actual header row by looking for expected column names
                header_row_idx = 0
                expected_headers = ["s no", "school name", "district", "block", "address"]
                
                for idx, row in all_sheets.iterrows():
                    row_lower = [str(c).strip().lower() for c in row]
                    # Check if this row contains most of the expected headers
                    matches = sum(1 for h in expected_headers if any(h in cell for cell in row_lower))
                    if matches >= 2:  # At least 2 expected headers
                        header_row_idx = idx
                        logger.info(f"Found header row at index {idx}: {row.tolist()}")
                        break
                
                # Read Excel again with the correct header row
                df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=header_row_idx)
                logger.info(f"Excel parsed: {len(df)} rows, columns: {list(df.columns)}")
                if df.empty:
                    raise HTTPException(status_code=400, detail="Excel file is empty or no data found")
            elif filename.endswith(".pdf"):
                # Parse PDF table with flexible column detection
                # Expected columns: S NO, DISTRICT, BLOCK NAME, SCHOOL NAME, SCHOOL ADDRESS, PINCODE
                import pdfplumber
                with pdfplumber.open(io.BytesIO(content)) as pdf:
                    all_rows = []
                    for page in pdf.pages:
                        table = page.extract_table()
                        if table:
                            all_rows.extend(table)
                    
                    if not all_rows or len(all_rows) < 2:
                        raise HTTPException(
                            status_code=400,
                            detail="No valid table found in PDF (need at least header and 1 data row)",
                        )
                    
                    # Try to detect header row and map columns flexibly
                    header_row = all_rows[0]
                    header_lower = [str(h).strip().lower() if h else "" for h in header_row]
                    
                    # Find column indices for key fields
                    school_name_idx = None
                    district_idx = None
                    block_idx = None
                    address_idx = None
                    pincode_idx = None
                    
                    for idx, h in enumerate(header_lower):
                        if "school" in h and "name" in h:
                            school_name_idx = idx
                        elif "district" in h:
                            district_idx = idx
                        elif "block" in h:
                            block_idx = idx
                        elif "address" in h:
                            address_idx = idx
                        elif "pincode" in h or "pin" in h:
                            pincode_idx = idx
                    
                    # Fallback to positional indexing if headers not found
                    # Standard format: S NO, DISTRICT, BLOCK NAME, SCHOOL NAME, SCHOOL ADDRESS, PINCODE
                    if school_name_idx is None:
                        school_name_idx = 3 if len(header_row) > 3 else 0
                    if district_idx is None:
                        district_idx = 1 if len(header_row) > 1 else None
                    if block_idx is None:
                        block_idx = 2 if len(header_row) > 2 else None
                    if address_idx is None:
                        address_idx = 4 if len(header_row) > 4 else None
                    if pincode_idx is None:
                        pincode_idx = 5 if len(header_row) > 5 else None
                    
                    data = []
                    for row in all_rows[1:]:  # Skip header row
                        if not row or not any(str(cell).strip() for cell in row):
                            continue  # Skip empty rows
                        
                        try:
                            school_name = str(row[school_name_idx]).strip() if school_name_idx is not None and school_name_idx < len(row) and row[school_name_idx] else None
                            
                            # Skip rows without valid school name
                            if not school_name or school_name.lower() == "nan":
                                continue
                            
                            district = str(row[district_idx]).strip() if district_idx is not None and district_idx < len(row) and row[district_idx] else None
                            block = str(row[block_idx]).strip() if block_idx is not None and block_idx < len(row) and row[block_idx] else None
                            address = str(row[address_idx]).strip() if address_idx is not None and address_idx < len(row) and row[address_idx] else None
                            pincode = str(row[pincode_idx]).strip() if pincode_idx is not None and pincode_idx < len(row) and row[pincode_idx] else None
                            
                            data.append({
                                "name": school_name,
                                "district": district,
                                "block": block,
                                "school_address": address,
                                "pincode": pincode,
                            })
                        except (IndexError, AttributeError, ValueError) as e:
                            errors.append(f"Row {len(data) + 1}: Failed to parse - {str(e)}")
                            continue
                    
                    if not data:
                        raise HTTPException(
                            status_code=400,
                            detail="No valid data rows found in PDF after applying column mapping",
                        )
                    
                    df = pd.DataFrame(data)
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file format. Please upload CSV, Excel (.xlsx/.xls), or PDF.",
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

        # Normalize and validate dataframe
        if df is None or df.empty:
            raise HTTPException(
                status_code=400,
                detail="No data found in uploaded file",
            )

        logger.info(f"Dataframe columns before normalization: {list(df.columns)}")

        # Normalize column names for CSV/Excel (PDF already has normalized columns)
        if not filename.endswith(".pdf"):
            # Convert column names to lowercase and replace spaces with underscores
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            logger.info(f"Dataframe columns after normalization: {list(df.columns)}")

            # Map CSV/Excel column names to our schema
            column_mapping = {
                "school_name": "name",
                "block_name": "block",
                "school_address": "school_address",
                "pincode": "pincode",
                "district": "district",
                "s_no": None,  # Skip S NO column
            }
            
            for old_col, new_col in column_mapping.items():
                if old_col in df.columns:
                    if new_col is None:
                        # Drop S NO column
                        df = df.drop(columns=[old_col])
                        logger.info(f"Dropped column: {old_col}")
                    elif new_col not in df.columns:
                        df = df.rename(columns={old_col: new_col})
                        logger.info(f"Renamed column: {old_col} → {new_col}")
            
            logger.info(f"Dataframe columns after mapping: {list(df.columns)}")

        # Clean data - ensure name column exists
        if "name" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="File must have a 'name', 'school_name', or 'SCHOOL NAME' column.",
            )

        # Fill missing optional columns with None (not empty string)
        for col in ["block", "district", "school_address", "pincode", "state"]:
            if col not in df.columns:
                df[col] = None

        # Remove rows where name is missing or empty
        logger.info(f"Before cleaning: {len(df)} rows in dataframe")
        df["name"] = df["name"].astype(str).str.strip()
        initial_count = len(df)
        df = df[df["name"].str.len() > 0]
        logger.info(f"After removing empty names: {len(df)} rows (filtered {initial_count - len(df)})")
        df = df[~df["name"].isin(["nan", "none", ""])]  # Better NaN filtering
        logger.info(f"After filtering nan/none: {len(df)} rows")

        if df.empty:
            logger.error("No valid school records found after filtering")
            raise HTTPException(
                status_code=400,
                detail="No valid school records found in file (after filtering empty names)",
            )

        inserted = 0
        skipped = 0
        total = len(df)
        logger.info(f"Starting insertion loop: {total} rows to process")
        logger.info(f"Available columns in dataframe: {list(df.columns)}")

        for idx, row in df.iterrows():
            # Check if name column exists, otherwise look for school_name
            name_col = "name" if "name" in df.columns else "school_name"
            if name_col not in df.columns:
                logger.error(f"NAME column not found. Available columns: {list(df.columns)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"NAME column not found after normalization. Available: {list(df.columns)}"
                )
            
            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None
            if not name or name == "nan":
                skipped += 1
                logger.debug(f"Skipping row {idx}: invalid name '{name}'")
                continue

            block = str(row.get("block", "")).strip() if "block" in row and pd.notna(row.get("block")) else None
            district = str(row.get("district", "")).strip() if "district" in row and pd.notna(row.get("district")) else None
            school_address = str(row.get("school_address", "")).strip() if "school_address" in row and pd.notna(row.get("school_address")) else None
            
            # Sanitize pincode - ensure it's max 6 characters (extract digits or take first 6 chars)
            pincode_raw = str(row.get("pincode", "")).strip() if "pincode" in row and pd.notna(row.get("pincode")) else None
            pincode = None
            if pincode_raw:
                # Try to extract numeric portion only
                digits = ''.join(c for c in pincode_raw if c.isdigit())
                pincode = digits[:6] if digits else pincode_raw[:6]
            
            state = str(row.get("state", "Tamil Nadu")).strip() if "state" in row and pd.notna(row.get("state")) else "Tamil Nadu"

            school = SchoolMaster(
                name=name,
                block=block,
                district=district,
                school_address=school_address,
                pincode=pincode,
                state=state,
            )
            self.db.add(school)
            inserted += 1
            logger.debug(f"Added school {inserted}: {name}")

        logger.info(f"Insertion loop complete: {inserted} schools added, {skipped} skipped")
        if inserted > 0:
            await self.db.commit()

        # Track the upload
        upload_record = SchoolListUpload(
            file_name=filename,
            record_count=inserted,
            upload_status="completed" if not errors else "partial",
        )
        self.db.add(upload_record)
        await self.db.commit()

        result = {
            "total_rows": total,
            "record_count": inserted,
            "skipped": skipped,
            "errors": errors,
        }
        logger.info(f"Upload completed: {result}")
        return result
