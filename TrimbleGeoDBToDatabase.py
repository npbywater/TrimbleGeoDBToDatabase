# Written by Scott D. Miller
# National Park Service, Arctic Inventory and Monitoring programs
# Shallow Lakes Monitoring Protocol
# https://www.nps.gov/im/cakn/shallowlakes.htm
# Purpose: Import field data into the lakes monitoring database. This python script translates the field data in the geodatabase 
# generated by the Shallow Lakes monitoring Trimble field computer
# into a series of SQL insert scripts that can be executed against the lakes monitoring database.
# U.S. Government Public Domain License

# Import utilities
import getpass
import datetime  
import os
    
# ArcTool input parameters
#GeoDB = arcpy.GetParameterAsText(0) # ArcTool parameter # 1: The input geodatabase (Workspace).
GeoDB = "C:/Work/VitalSigns/ARCN-CAKN Shallow Lakes/Local/2020-07 Geodatabase/2020/YUCH_2020/YUCH_2020_Deployment.gdb"

# Set the workspace
arcpy.env.workspace = GeoDB

# Get the name of the geodatabase from the full path of the source geodatabase
SourceFilename = os.path.basename(GeoDB) # Extract just the filename from the path from above.

# Get the username
username = getpass.getuser()

# Standard header information to put in each sql script
HeaderInfo = "-- NPS Arctic and Central Alaska Inventory and Monitoring Program, Shallow Lakes Monitoring\n\n"
#HeaderInfo = HeaderInfo + "Source geodatabase: " + GeoDB + "\n*/\n\n"




# Translates the data in the Secchi_Joined featureclass into a script of SQL insert queries that can be executed on the AK_ShallowLakes database.
# NOTE: secchi depth is stored in the tblEvents table so this script tries to create a new event. There is no Secchi depth table in the database.
# Since events must be present to insert the other records this script must be run first.
# This may not be what you expect.
def Export_Secchi_Joined():
    try:
        FeatureClass = "Secchi_Joined"

        # This will be the output SQL file, same directory as the source geodatabase.
        SqlFile = os.path.dirname(arcpy.env.workspace) + '/' + SourceFilename + '_' + FeatureClass + '_Insert.sql'
        
        # if the SQL file exists already then delete it 
        if os.path.exists(SqlFile):
            arcpy.AddMessage("File exists: " + SqlFile + '. Deleted')
            os.remove(SqlFile)
        SqlFile = open(SqlFile,'a')  

        # Get the featureclass' field names
        Fields = arcpy.ListFields(FeatureClass)
        Field_names =  [Field.name for Field in Fields]

        # We need to ensure all the lakes exist before we can create sampling events, this variable will hold that checking code.
        LakeExistQueries = "-- All the lakes in the input geodatabase must exist in tblPonds before events can be created or updated\n "
        LakeExistQueries = LakeExistQueries + "IF "

        #Write a query to allow the user to preview the secchi data that may be overwritten
        PreviewQuery = "SELECT PONDNAME, SAMPLEDATE, SECCHIDEPTH, SECCHIONBOTTOM, SECCHINOTES FROM tblEvents WHERE "

        # Insert queries
        InsertQueries = ""

        # loop through the data rows and translate the data cells into an SQL insert query
        for row in arcpy.da.SearchCursor(FeatureClass,Field_names):
            i = 0

            # Get the field values into variables
            PondName = str(row[11])
            SampleDate = str(row[8])
            SECCHIDEPTH = str(row[5])
            if row[6] == "Yes":
                SECCHIONBOTTOM = '1' ''
            else: 
                SECCHIONBOTTOM = '0'
            SECCHINOTES = str(row[7])
            SampleDateShort = GetShortDate(SampleDate) # Events in tblEvents should only have a date, not a datetime, this strips the time part off the sample date
            
            # Validate that the lake exists
            LakeExistQueries = LakeExistQueries + "EXISTS\n (SELECT PondName FROM tblPonds WHERE Pondname = '" + PondName + "') And "

            # Write the insert query to file
            # NOTE: Secchi data is stored in tblEvents so the SQL ensures the event exists.
            SelectQuery = "SELECT  PONDNAME, SAMPLEDATE, SECCHIDEPTH, SECCHIONBOTTOM, SECCHINOTES FROM tblEvents WHERE Pondname = '" + PondName + "' And Convert(Datetime,SampleDate,102) = '" + SampleDateShort + "'"
            InsertQueries = InsertQueries + "       -- Ensure the Event for these data edits exists.\n"
            InsertQueries = InsertQueries + "       IF EXISTS (" + SelectQuery + ")\n"
            InsertQueries = InsertQueries + "               -- The event exists, update it.\n"
            InsertQueries = InsertQueries + "               UPDATE tblEvents SET SECCHIDEPTH = " + SECCHIDEPTH + ", SECCHIONBOTTOM = " + SECCHIONBOTTOM + ", SECCHINOTES = '" + SECCHINOTES + "' WHERE Pondname = '" + PondName + "' And SampleDate = '" + SampleDateShort + "'\n\n"
            InsertQueries = InsertQueries + "               -- The event does not exist. If you want to insert it then uncomment the INSERT query below and execute.\n"
            InsertQueries = InsertQueries + "               -- INSERT INTO tblEvents(PONDNAME,SAMPLEDATE,SECCHIDEPTH,SECCHIONBOTTOM,SECCHINOTES) VALUES('" + PondName + "','" + SampleDateShort + "'," + SECCHIDEPTH + "," + SECCHIONBOTTOM + ",'" + SECCHINOTES + "');\n\n"
            InsertQueries = InsertQueries + "               -- Utility SELECT query in case you want to manually see the event. Uncomment and execute.\n"
            InsertQueries = InsertQueries + "               -- " + SelectQuery + "\n\n"
            InsertQueries = InsertQueries + "       ELSE\n"
            InsertQueries = InsertQueries + "           PRINT 'The event for this record does not exist. PondName:" + PondName + " SampleDate: " + SampleDateShort + "'\n\n"
            
            PreviewQuery = PreviewQuery + " (Pondname = '" + PondName + "' And Convert(Datetime,SampleDate,102) = '" + SampleDateShort + "') Or "

        # Write the header info to file
        SqlFile.write(HeaderInfo)
        SqlFile.write("/*\n")
        SqlFile.write("Purpose: Transfer secchi depth data from the field Trimble data collection application to the AK_ShallowLakes monitoring SQL Server database.\n")
        SqlFile.write("Source geodatabase: " + GeoDB  + "\n") 
        SqlFile.write("FeatureClass: " + FeatureClass  + "\n") 
        SqlFile.write("SQL file name : " + SqlFile.name + "\n\n")
        SqlFile.write("Script generated by: " + username + ".\n")
        SqlFile.write("Datetime: " + str(datetime.datetime.now())  + ".\n")
        SqlFile.write("*/\n\n")
        
        # Inform the sql file executed
        

        SqlFile.write("/*\nREAD AND THOROUGHLY UNDERSTAND THIS SCRIPT BEFORE RUNNING.\nRunning this script may change records in the Shallow Lakes monitoring database.\nThe lakes referenced in this script must exist in the tblPonds table prior to running this script. \nSecchi depth data is stored in tblEvents. \nOn error, rollback and correct any problems, then run again. Commit changes when finished.\n*/\n\n")
        SqlFile.write("USE AK_ShallowLakes\n\n")
       
        SqlFile.write("-- PREVIEW OF AFFECTED RECORDS: To see the secchi depth values that may be affected uncomment and run the query below:\n")
        SqlFile.write("-- " + PreviewQuery[:len(PreviewQuery) - 4] + "\n\n")
       
        SqlFile.write("BEGIN TRANSACTION -- COMMIT ROLLBACK -- All queries in this transaction must succeed or fail together. COMMIT if all queries succeed. ROLLBACK if any fail. Failure to COMMIT or ROLLBACK will leave the database in a hanging state.\n\n")
        
        

        SqlFile.write(LakeExistQueries[:len(LakeExistQueries) - 4] + "\n    BEGIN\n") # Trim the trailing ' And'
        SqlFile.write(InsertQueries)
        SqlFile.write("    END\n")
        SqlFile.write("ELSE\n")
        SqlFile.write("    PRINT 'ERROR: One or more lakes are missing from tblPonds. All lakes in the insert query block must exist in tblPonds before sampling events can be created in the tblEvents table.'\n")

        # Let user know we're done
        FinishedMessage = FeatureClass + " data written to " + SqlFile.name.replace("/","\\"+ "\n")
        print(FinishedMessage)
        arcpy.AddMessage(FinishedMessage)

    # When something goes wrong, let user know
    except Exception as e:
        error = 'Error: ' + FeatureClass + ' ' + str(e)
        arcpy.AddMessage(error)
        print(error)


# Translates the data in the Depth_Joined featureclass into a script of SQL insert queries that can be executed on the AK_ShallowLakes database.
def Export_Depth_Joined():
    try:
        FeatureClass = "Depth_Joined"

        # This will be the output SQL file, same directory as the source geodatabase.
        SqlFile = os.path.dirname(arcpy.env.workspace) + '/' + SourceFilename + '_' + FeatureClass + '_Insert.sql'
        
        # if the SQL file exists already then delete it 
        if os.path.exists(SqlFile):
            arcpy.AddMessage("File exists: " + SqlFile + '. Deleted')
            os.remove(SqlFile)
        SqlFile = open(SqlFile,'a')  

        # Create the first half of the SQL insert query
        SqlPrefix = 'INSERT INTO tblPondDepths(PONDNAME,SAMPLEDATE,GPS_TIME,LATITUDE,LONGITUDE,DEPTH,COMMENTS_DEPTHS,DATAFILE,SOURCE) VALUES('
        
        # Get the featureclass' field names
        Fields = arcpy.ListFields(FeatureClass)
        Field_names =  [Field.name for Field in Fields]

        # Write the header info to file
        SqlFile.write(HeaderInfo)
        SqlFile.write("BEGIN TRANSACTION -- COMMIT ROLLBACK\n")

        # loop through the data rows and translate the data cells into an SQL insert query
        for row in arcpy.da.SearchCursor(FeatureClass,Field_names):
            i = 0

            # Get the field values into variables
            PondName = str(row[10])
            SampleDate = str(row[7])
            GPS_Time = str(row[7])
            Latitude = str(row[9])
            Longitude = str(row[8])
            Depth = str(row[4])
            Comments_Depths = str(row[5])
            DataFile = SourceFilename
            Source = SourceFilename
            SampleDateShort = GetShortDate(SampleDate) # Events in tblEvents should only have a date, not a datetime, this strips the time part off the sample date

            # Write the insert query to file
            SqlFile.write(SqlPrefix + "'" + PondName + "','" + SampleDateShort + "','" + GPS_Time + "'," + Latitude + "," + Longitude + "," + Depth + ",'" + Comments_Depths + "','" + DataFile + "','" + Source + "');\n")

        # Write convenience commit/rollback options    
        SqlFile.write("\n-- COMMIT\n-- ROLLBACK")

        # Let user know we're done
        FinishedMessage = FeatureClass + " data written to " + SqlFile.name.replace("/","\\" + "\n")
        print(FinishedMessage)
        arcpy.AddMessage(FinishedMessage)

    # When something goes wrong, let user know
    except expression as identifier:
        error = 'Error: ' + FeatureClass + ' ' + str(e)
        arcpy.AddMessage(error)
        print(error)

# Translates the data in the Loons_Joined featureclass into a script of SQL insert queries that can be executed on the AK_ShallowLakes database.
# NOTE: secchi depth is stored in the tblEvents table so this script tries to create a new event. There is no Secchi depth table in the database.
# Since events must be present to insert the other records this script must be run first.
# This may not be what you expect.
def Export_Loons_Joined(): 
    try:
        FeatureClass = "Loons_Joined"

        # This will be the output SQL file, same directory as the source geodatabase.
        SqlFile = os.path.dirname(arcpy.env.workspace) + '/' + SourceFilename + '_' + FeatureClass + '_Insert.sql'
        
        # if the SQL file exists already then delete it 
        if os.path.exists(SqlFile):
            arcpy.AddMessage("File exists: " + SqlFile + '. Deleted')
            os.remove(SqlFile)
        SqlFile = open(SqlFile,'a')  

        # Create the first half of the SQL insert query
        SqlPrefix = 'INSERT INTO tblLoons(PONDNAME,SAMPLEDATE,SPECIES,NUM_ADULTS,NUM_YOUNG,DETECTION_TYPE,LATITUDE,LONGITUDE,COMMENTS,SOURCE) VALUES('
        
        # Get the featureclass' field names
        Fields = arcpy.ListFields(FeatureClass)
        Field_names =  [Field.name for Field in Fields]

        # Write the header info to file
        SqlFile.write(HeaderInfo)
        SqlFile.write("BEGIN TRANSACTION -- COMMIT ROLLBACK\n")

        # loop through the data rows and translate the data cells into an SQL insert query
        for row in arcpy.da.SearchCursor(FeatureClass,Field_names):
            i = 0

            # Get the field values into variables
            PondName = str(row[13])
            SampleDate = str(row[10])
            # OBSERVER = str(row[8])
            SPECIES = str(row[4])
            NUM_ADULTS = str(row[6])
            NUM_YOUNG = str(row[7])
            DETECTION_TYPE = str(row[5])
            LATITUDE = str(row[12])
            LONGITUDE = str(row[11])
            # VEG_TYPE = str(row[8])
            COMMENTS = str(row[9])
            SOURCE = SourceFilename
            SampleDateShort = GetShortDate(SampleDate) # Events in tblEvents should only have a date, not a datetime, this strips the time part off the sample date

            # Write the insert query to file
            SqlFile.write(SqlPrefix + "'" + PondName + "','" + SampleDateShort + "','" + SPECIES + "'," + NUM_ADULTS + "," + NUM_YOUNG + ",'" + DETECTION_TYPE + "'," + LATITUDE + "," + LONGITUDE + ",'" + COMMENTS + "','" + SOURCE + "');\n")

        # Write convenience commit/rollback options    
        SqlFile.write("\n-- COMMIT\n-- ROLLBACK")

        # Let user know we're done
        FinishedMessage = FeatureClass + " data written to " + SqlFile.name.replace("/","\\"+ "\n")
        print(FinishedMessage)
        arcpy.AddMessage(FinishedMessage)

    # When something goes wrong, let user know
    except e:
        error = 'Error: ' + FeatureClass + ' ' + str(e)
        arcpy.AddMessage(error)
        print(error)


def GetShortDate(LongDate):
    TheDate = datetime.datetime.strptime(LongDate, '%Y-%m-%d %H:%M:%S')
    ShortDate = str(TheDate.year) + "-" + str(TheDate.month) + "-" + str(TheDate.day)
    return ShortDate


# start here
#Export_CheckPondsExist()
Export_Secchi_Joined()
Export_Depth_Joined()
Export_Loons_Joined()





