# Updated crud.py
# Now handles roles and screen-specific permissions.
from sqlalchemy.ext.asyncio import AsyncSession

from components.db.db import get_db_session

# Function to insert 1000 institution records
async def insert_bulk_institutions(db: AsyncSession):
    """
    Insert 1000 institution records into the database.
    Each institution will have a unique code and name.
    """
    from common.models.auth.user import Institution
    
    institutions = []
    for i in range(1, 1001):
        institution = Institution(
            code=f"INST{i:04d}",  # INST0001, INST0002, etc.
            name=f"Institution {i}",
            is_active=True
        )
        institutions.append(institution)
    
    # Add each instance and commit
    for institution in institutions:
        db.add(institution)
    await db.commit()
    
    # Refresh all objects to get their IDs
    for institution in institutions:
        await db.refresh(institution)
    
    print(f"Successfully inserted {len(institutions)} institutions")
    return institutions

async def main():
    # get_db_session is a dependency generator; iterate it to obtain an AsyncSession
    async for db in get_db_session():
        await insert_bulk_institutions(db)
        break

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())