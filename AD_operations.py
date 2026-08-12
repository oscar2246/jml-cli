from ldap3 import Server, Connection, MODIFY_REPLACE
from ldap3.utils.conv import escape_filter_chars
import secrets_local
ACCOUNTDISABLE = 0x0002

def initialize_connection():


    server = Server(f"ldaps://{secrets_local.DC_host_ip}", use_ssl=True)

    conn = Connection(
        server,
        user=secrets_local.SVC_Account_AD,
        password=secrets_local.SVC_PW,
        auto_bind=True,   
    )

    return conn

def search_user_AD(conn, sAMAccountName_search):
     
     safe_name = escape_filter_chars(sAMAccountName_search)
     conn.search(
                secrets_local.SEARCH_BASE, 
                    f'(&(ObjectClass=user)(objectCategory=Person)(sAMAccountName={safe_name}))', 
                    attributes=['sAMAccountName', 'mail', 'userAccountControl'],
    )

     return conn.entries

def check_email_existence(conn, Email):
     
     safe_name_email = escape_filter_chars(Email)

     conn.search(
          secrets_local.SEARCH_BASE,
          f'(&(ObjectClass=user)(ObjectCategory=Person)(mail={safe_name_email}))'
     )
     return bool(conn.entries)

def check_lan_existence(conn, lan):
     
     safe_name_lan = escape_filter_chars(lan)

     conn.search(
          secrets_local.SEARCH_BASE,
          f'(&(ObjectClass=user)(ObjectCategory=Person)(sAMAccountName={safe_name_lan}))'
     )
     return bool(conn.entries)

def get_user_AD(conn, lan):
     safe_name_lan = escape_filter_chars(lan)

     conn.search(
          secrets_local.SEARCH_BASE,
          f'(&(ObjectClass=user)(ObjectCategory=Person)(sAMAccountName={safe_name_lan}))',
          attributes=['userAccountControl']
     )
     if conn.entries:
          uac_number = int(conn.entries[0].userAccountControl.value)
          user_dn = conn.entries[0].entry_dn
          return user_dn, uac_number
     else:
          return None, None
     
def modify_account_status(conn, lan, enable):
     dn, uac = get_user_AD(conn, lan)
     if dn:
          if enable:
               new_uac = uac & ~ACCOUNTDISABLE
          else:
               new_uac = uac | ACCOUNTDISABLE
          conn.modify(dn, {'userAccountControl': [(MODIFY_REPLACE,[new_uac])]})
          return conn.result['result'] == 0
     else:
          return False
     
def create_user_AD(conn, f_name, m_name, l_name, LANID, email):

     m_initial = m_name[0] if m_name else ""
     middle = f" {m_initial}." if m_name else ""
     display_name = f"{l_name.capitalize()}, {f_name.capitalize()}{middle}"
     dn = (f"CN={LANID},{secrets_local.SEARCH_BASE}")
     conn.add(dn, object_class='user', attributes={'sAMAccountName':LANID,
                                                    'userPrincipalName':email,
                                                    'givenName': f_name,
                                                    'sn':l_name,
                                                    'displayName':display_name,
                                                    'userAccountControl': 514
     })
     return conn.result['result'] == 0

def set_password(conn, lan, pw):
     dn, uac = get_user_AD(conn, lan)
     if dn:
          conn.modify(dn, {'unicodePwd': [(MODIFY_REPLACE, [f'"{pw}"'.encode('utf-16-le')])]})
          return conn.result['result'] == 0
     else: return False

def force_change_password(conn, lan, force):
    
    dn, uac = get_user_AD(conn, lan)
    if dn:
         if force:
              conn.modify(dn, {'pwdLastSet': [(MODIFY_REPLACE, [0])]})
              return conn.result['result'] == 0
         else:
              conn.modify(dn, {'pwdLastSet': [(MODIFY_REPLACE, [-1])]})
              return conn.result['result'] == 0 
    else: return False
