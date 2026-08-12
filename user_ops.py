from uuid import uuid4
import AD_operations
import secrets_local
import storage
import password_gen

conn = AD_operations.initialize_connection()


def search_user():
    user_search = input("Please enter the sAMAccountName of the user you wish to search: ")
    results = AD_operations.search_user_AD(conn, user_search)
    if results:
        print(results[0])
    else:
        print("No user found")
                     
def gather_information():
    print("\n --- User Creation --- ")
    
    #User information gathering
    f_name = input("Enter First Name: ").strip()
    m_name = input("Enter Middle Name: ").strip()
    l_name = input("Enter Last Name: ").strip()



    if not f_name or not l_name:
        print("First and Last Name are required")
        return
    
    information = (f_name, m_name, l_name)

    return information
    
class user_creation:
    
    def __init__(self, f_name, m_name, l_name, conn):
            self.f_name = f_name
            self.m_name = m_name
            self.l_name = l_name
            self.user_id = str(uuid4())
            self.account_status = "disabled"
            self.set_lan(conn)
            self.set_email(conn)

    def set_lan(self,  conn):
        
        #LANID generation
        base_lan_id = (f"{self.f_name[:4]}{self.m_name[:1]}{self.l_name[:2]}").upper()
        LANID = base_lan_id
        l_counter = 1
        
        while AD_operations.check_lan_existence(conn, LANID):
            LANID = f"{base_lan_id}{l_counter}"
            l_counter += 1

        self.LANID = LANID
    
    def set_email(self, conn):
        #Email generation
        base_email_local = f"{self.f_name}.{self.l_name}"
        domain = secrets_local.domain
        email = f"{base_email_local}@{domain}".lower()
        e_counter = 1
    
        while AD_operations.check_email_existence(conn, email):
            #if John.doe@example.internal exists then it will use john.doe1@example.com, avoiding collision
            email = f"{base_email_local}{e_counter}@{domain}".lower()
            e_counter += 1
        self.email = email


def create_user():
    users = storage.load_users()
    information = gather_information()
    

    if information == None:
        print("Information comes back as None")
        return

    f_name = information[0]
    m_name = information[1]
    l_name = information[2]

    new_user_obj = user_creation(f_name, m_name, l_name, conn)
    temp_password = password_gen.generate()
    #grouping all new user information
    new_user = {
        "Last Name": l_name,
        "First Name": f_name,
        "Middle Name": m_name,
        "Email": new_user_obj.email,
        "LANID": new_user_obj.LANID,
        "user_id": new_user_obj.user_id,
        "Account Status": new_user_obj.account_status
    }
    if not AD_operations.create_user_AD(conn, f_name, m_name, l_name, new_user_obj.LANID, new_user_obj.email):
        print("AD account creation failed")
        return

    if not AD_operations.set_password(conn, new_user_obj.LANID, temp_password):
        print("password change failed")
        return 
    
    if not AD_operations.force_change_password(conn, new_user_obj.LANID, True):
        print("force password change failed")
        return



    users.append(new_user)
    storage.save_users(users)
    storage.log_event("CREATED", new_user_obj.LANID)

    m_initial = m_name[0].capitalize() if m_name else ""
    
    print(f"\nSuccessfully created account for {l_name}, {f_name} {m_initial}")
    print(f"Email: {new_user_obj.email}")
    print(f"LANID: {new_user_obj.LANID}")
    print(f"User ID: {new_user_obj.user_id}")
    print(f"Account Status: {new_user_obj.account_status}")
    print(f"Temporary password: {temp_password}")

def list_users():
    print(" --- Users --- ")
    users = storage.load_users()
    if not users:
        print("No users found.")
        return
        
    for i, user in enumerate(users, 1):
        print(f"{i}. {user['Last Name']}, {user['First Name']} | LANID: {user['LANID']} | Email: {user['Email']} | User ID: {user['user_id']} | Account Status: {user['Account Status']}")

def disable_user():

    print(" --- Disable User --- ")
    
    users = storage.load_users()
    found = False
    lan_id_input = input("Please enter the LAN ID of the user you wish to disable: ").strip().upper()
    for user in users:
        if user['LANID'].upper() == lan_id_input:
            found = True
            print(f"{user['First Name']}, {user['Last Name']}")
            print(f"{user['Email']}")
            answer = input("Y/N: ").strip().upper()
            if answer == "Y":
                if user['Account Status'] == "disabled":
                    print("Account is already disabled")
                    break
                if AD_operations.modify_account_status(conn, user['LANID'], False):
                    user['Account Status'] = "disabled"
                    storage.save_users(users)
                    storage.log_event("DISABLED", user['LANID'])
                    print(f"Disabled {user['LANID']}")
                else:
                    print("User Disable operation failed")
            else:
                print("Aborted")
                break
    if found != True:
        print(f"{lan_id_input} User not found")

def enable_user():

    print(" --- Enable User ---")

    users = storage.load_users()
    found = False
    lan_id_input = input("Please enter the LAN ID of the user you wish to enable: ").strip().upper()
    for user in users:
        if user['LANID'].upper() == lan_id_input:
            found = True
            print(f"{user['First Name']}, {user['Last Name']}")
            print(f"{user['Email']}")
            answer = input("Y/N: ").strip().upper()
            if answer == "Y":
                if user['Account Status'] == "enabled":
                    print("User is already enabled")
                    break
                if AD_operations.modify_account_status(conn, user['LANID'], True):
                    user['Account Status'] = "enabled"
                    storage.save_users(users)
                    storage.log_event("ENABLED", user['LANID'])
                    print(f"Enabled {user['LANID']}")
                else:
                    print("User Enable operation failed")
            else:
                print("Aborted")
                break
    if found != True:
        print(f"{lan_id_input} User not found")
