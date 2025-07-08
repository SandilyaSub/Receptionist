import os
import json
from supabase_client import get_supabase_client

def check_tenant_config(tenant_id: str):
    """Check if a tenant exists and is active in the database."""
    try:
        # Get Supabase client
        supabase = get_supabase_client()
        
        # Query the tenant_configs table
        response = supabase.table('tenant_configs') \
            .select('*') \
            .eq('tenant_id', tenant_id) \
            .execute()
        
        if response.data and len(response.data) > 0:
            tenant_config = response.data[0]
            print(f"✅ Tenant '{tenant_id}' found in database")
            print("\nTenant Configuration:")
            print(json.dumps(tenant_config, indent=2))
            
            # Check if tenant is active
            is_active = tenant_config.get('is_active', False)
            if is_active:
                print("\n✅ Tenant is ACTIVE")
            else:
                print("\n❌ Tenant is INACTIVE")
                
            # Check for required prompt files
            check_prompt_files(tenant_id)
            
        else:
            print(f"❌ Tenant '{tenant_id}' not found in database")
            
    except Exception as e:
        print(f"❌ Error checking tenant configuration: {str(e)}")
        raise

def check_prompt_files(tenant_id: str):
    """Check if required prompt files exist for the tenant."""
    base_dir = os.path.join('tenant_repository', tenant_id, 'prompts')
    required_files = ['assistant.txt', 'analyzer.txt']
    
    print("\nChecking prompt files:")
    all_files_exist = True
    
    for file_name in required_files:
        file_path = os.path.join(base_dir, file_name)
        if os.path.exists(file_path):
            print(f"✅ Found {file_name}")
        else:
            print(f"❌ Missing {file_name} at {file_path}")
            all_files_exist = False
    
    if all_files_exist:
        print("\n✅ All required prompt files are present")
    else:
        print("\n❌ Some prompt files are missing")

if __name__ == "__main__":
    tenant_id = "joy_invite"
    print(f"Checking configuration for tenant: {tenant_id}")
    check_tenant_config(tenant_id)
