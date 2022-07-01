import psycopg2
from psycopg2 import Error
from pathlib import Path

try:
    # Connect to an existing database
    connection = psycopg2.connect(user="postgres",
                                  #password="",
                                  host="db",
                                  port="5432",
                                  database="webodm_dev")

    # Create a cursor to perform database operations
    cursor = connection.cursor()
    # Print PostgreSQL details
    print("PostgreSQL server information")
    print(connection.get_dsn_parameters(), "\n")
    # Executing a SQL query
    cursor.execute("SELECT version();")
    # Fetch result
    record = cursor.fetchone()
    print("You are connected to - ", record, "\n")

    # Executing a SQL query
    cursor.execute("SELECT id from app_project order by id;")
    # Fetch result
    records = cursor.fetchall()
    #print("Auth users:", records, "\n")
    for row in records:
        #print("Id = ", row[0], )
        #print("UName = ", row[1])
        pr_id = row[0]
        cursor.execute(f"select id from app_task where project_id = {pr_id};")
        tasklist = [e[0] for e in cursor.fetchall()]
        #print(tasklist)
        dirname = Path(f"/webodm/app/media/project/{pr_id}/task/")
        if dirname.exists():
            fu = [f for f in dirname.iterdir() if f.is_dir()]
            #print(fu)
            for t in fu:
                if not t.stem in tasklist:
                    print(f"{t} not found in tasks!")

except (Exception, Error) as error:
    print("Error while connecting to PostgreSQL", error)
finally:
    if (connection):
        cursor.close()
        connection.close()
        print("PostgreSQL connection is closed")
