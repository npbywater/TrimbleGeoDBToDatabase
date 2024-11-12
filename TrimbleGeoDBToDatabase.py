# Written by Scott D. Miller, improved by Nick Bywater
# National Park Service, Arctic and Central Alaska Inventory and Monitoring programs
# Shallow Lakes Monitoring Protocol
# https://www.nps.gov/im/cakn/shallowlakes.htm

# Purpose:
# Import field data into the lakes monitoring database. This python
# script translates the field data in the geodatabase generated by the
# Shallow Lakes monitoring Trimble field computer into a series of SQL
# insert scripts that can be executed against the lakes monitoring
# database.

# U.S. Government Public Domain License

# Import utilities
import arcpy
import getpass
import datetime
import os
import TrimbleUtility

def ExportSecchiJoined():
    """
    Translates the data in the Secchi_Joined featureclass into a
    script of SQL insert queries that can be executed on the
    AK_ShallowLakes database.

    NOTE: secchi depth is stored in the tblEvents table so this script
    the event must exist before the Secchi columns are updated. There
    is no Secchi depth table in the database.
    """
    try:
        GEO_DB_PATH = arcpy.env.workspace

        AssertGeoDB(GEO_DB_PATH)

        SOURCE_FILE_NAME = os.path.basename(GEO_DB_PATH) # Extract just the filename from the path.

        FEATURE_CLASS = "Secchi_Joined"

        DatetimeStr = TrimbleUtility.GetCurrentDatetimeStr()
        TARGET_FILE_NAME = SOURCE_FILE_NAME + '_' + FEATURE_CLASS + '_Insert_' + DatetimeStr +'.sql'

        SqlFilePath = os.path.dirname(arcpy.env.workspace) + '/' + TARGET_FILE_NAME

        SqlFile = open(SqlFilePath,'a')

        # We need to ensure all the lakes exist before we can create
        # sampling events, this variable will hold that checking code.
        LakeExistQueriesComments = "-- All the lakes in the input geodatabase must exist in tblPonds before events can be created or updated\n"
        LakeExistQueries = []

        # Write a query to allow the user to preview the secchi data
        # that may be overwritten
        PreviewQuery = "SELECT PONDNAME, SAMPLEDATE, SECCHIDEPTH, SECCHIONBOTTOM, SECCHINOTES FROM tblEvents WHERE \n"

        # Insert queries
        InsertQueries = []

        for Row in TrimbleUtility.GetFeatureClassRows(FEATURE_CLASS):
            PySampleDateTime = Row['CreationDateTimeLocal']

            # A record without a creation datetime is not a valid
            # record. End this iteration and go to the next row.
            if PySampleDateTime is None:
                continue

            PondName = str(Row['LakeNum'])
            SampleDate = TrimbleUtility.GetDateTime(PySampleDateTime, 'd')

            if Row['Secchi_Depth_in_meters'] is not None:
                SecchiDepth = str(round(Row['Secchi_Depth_in_meters'], 1))
            else:
                SecchiDepth = 'NULL'

            if Row['OnBottom'] == "Yes":
                SecchiOnBottom = '1'
            else:
                SecchiOnBottom = '0'

            SecchiNotes = Row['Comments'].strip()

            # Validate that the lake exists
            LakeExists = "EXISTS (SELECT PondName FROM tblPonds WHERE Pondname = '" + PondName + "') And \n"

            if len(LakeExistQueries) > 0:
                LakeExistQueries.append("    " + LakeExists)
            else:
                LakeExistQueries.append("IF " + LakeExists)

            # Write the insert query to file
            # NOTE: Secchi data is stored in tblEvents so the SQL
            # ensures the event exists.
            SelectQuery = "SELECT  PONDNAME, SAMPLEDATE, SECCHIDEPTH, SECCHIONBOTTOM, SECCHINOTES FROM tblEvents WHERE Pondname = '" + PondName + "' And SampleDate = '" + SampleDate + "'"
            InsertQueries.append("       -- Ensure the Event for these data edits exists.\n")
            InsertQueries.append("       IF EXISTS (" + SelectQuery + ")\n")
            InsertQueries.append("               -- The event exists, update it.\n")
            InsertQueries.append("               UPDATE tblEvents SET SECCHIDEPTH = " + SecchiDepth + ", SECCHIONBOTTOM = " + SecchiOnBottom + ", ")

            CommentStr = ("SECCHINOTES = NULL"  if SecchiNotes == '' else "SECCHINOTES = '" + SecchiNotes + "'")
            InsertQueries.append(CommentStr +
                                 " WHERE Pondname = '" + PondName + "' And SampleDate = '" + SampleDate + "'\n\n")

            InsertQueries.append("               -- The event does not exist. If you want to insert it then uncomment the INSERT query below and execute.\n")

            CommentStr = (",NULL);\n\n" if SecchiNotes == '' else ",'" + SecchiNotes + "');\n\n")
            InsertQueries.append("               -- INSERT INTO tblEvents(PONDNAME,SAMPLEDATE,SECCHIDEPTH,SECCHIONBOTTOM,SECCHINOTES) VALUES('" +
                                 PondName + "','" + SampleDate + "'," + SecchiDepth + "," + SecchiOnBottom +
                                 CommentStr)

            InsertQueries.append("               -- Utility SELECT query in case you want to manually see the event. Uncomment and execute.\n")
            InsertQueries.append("               -- " + SelectQuery + "\n\n")
            InsertQueries.append("       ELSE\n")
            InsertQueries.append("           PRINT 'The event for this record does not exist. PondName:" + PondName + " SampleDate: " + SampleDate + "'\n\n")

            PreviewQuery = PreviewQuery + "-- (Pondname = '" + PondName + "' And SampleDate = '" + SampleDate + "') Or \n"

        # Write the header info to file
        PURPOSE = "Transfer secchi depth data from the field Trimble data collection application to the AK_ShallowLakes monitoring SQL Server database."
        SqlFile.write(GetFileHeader(PURPOSE, GEO_DB_PATH, FEATURE_CLASS, SqlFile.name))

        SqlFile.write("/*\nREAD AND THOROUGHLY UNDERSTAND THIS SCRIPT BEFORE RUNNING.\nRunning this script may change records in the Shallow Lakes monitoring database.\nThe lakes referenced in this script must exist in the tblPonds table prior to running this script. \nSecchi depth data is stored in tblEvents. \nOn error, rollback and correct any problems, then run again. Commit changes when finished.\n*/\n\n")
        SqlFile.write("USE AK_ShallowLakes\n\n")

        SqlFile.write("-- PREVIEW OF AFFECTED RECORDS: To see the secchi depth values that may be affected uncomment and run the query below:\n")
        SqlFile.write("-- " + PreviewQuery[:len(PreviewQuery) - 4] + "\n\n")

        SqlFile.write("BEGIN TRANSACTION -- COMMIT ROLLBACK -- All queries in this transaction must succeed or fail together. COMMIT if all queries succeed. ROLLBACK if any fail. Failure to COMMIT or ROLLBACK will leave the database in a hanging state.\n\n")


        LakeExistWrite = LakeExistQueriesComments + ''.join(LakeExistQueries)
        SqlFile.write(LakeExistWrite[:len(LakeExistWrite) - 6] + "\nBEGIN\n") # Trim the trailing ' And'

        SqlFile.write(''.join(InsertQueries))
        SqlFile.write("END\n")
        SqlFile.write("ELSE\n")
        SqlFile.write("    PRINT 'ERROR: One or more lakes are missing from tblPonds. All lakes in the insert query block must exist in tblPonds before sampling events can be created in the tblEvents table.'\n")

        # Let user know we're done
        FinishedMessage = FEATURE_CLASS + " data written to: " + SqlFile.name + '\n'
        arcpy.AddMessage(FinishedMessage)

    except Exception as e:
        Error = 'Error in function ExportSecchiJoined: ' + str(e)
        arcpy.AddMessage(Error)

def ExportDepthJoined():
    """
    Translates the data in the Depth_Joined featureclass into a script
    of SQL insert queries that can be executed on the AK_ShallowLakes
    database.
    """
    try:
        GEO_DB_PATH = arcpy.env.workspace

        AssertGeoDB(GEO_DB_PATH)

        SOURCE_FILE_NAME = os.path.basename(GEO_DB_PATH) # Extract just the filename from the path.

        FEATURE_CLASS = "Depth_Joined"

        DatetimeStr = TrimbleUtility.GetCurrentDatetimeStr()
        TARGET_FILE_NAME = SOURCE_FILE_NAME + '_' + FEATURE_CLASS + '_Insert_' + DatetimeStr +'.sql'

        SqlFilePath = os.path.dirname(arcpy.env.workspace) + '/' + TARGET_FILE_NAME

        SqlFile = open(SqlFilePath,'a')

        # Create the first half of the SQL insert query
        SqlPrefix = 'INSERT INTO tblPondDepths(PONDNAME,SAMPLEDATE,GPS_TIME,LATITUDE,LONGITUDE,DEPTH,COMMENTS_DEPTHS,DATAFILE,SOURCE) VALUES('

        # This will hold the insert queries as they are built
        InsertQueries = ""

        # We need a query to determine if all the Events needed in the
        # new data to be imported exist in tblEvents or not Build up a
        # query to determine this.
        EventExistsQuery = "-- Determine if all the necessary parent Event records exist before trying to insert\nIF\n"

        # Build a query to select the just inserted records in order
        # to validate them
        ValidateQuery = "SELECT PONDNAME,SAMPLEDATE,GPS_TIME,LATITUDE,LONGITUDE,DEPTH,COMMENTS_DEPTHS,DATAFILE,SOURCE FROM tblPondDepths WHERE\n"

        # Write the header info to file
        PURPOSE = "Transfer lake depth data from the field Trimble data collection application to the AK_ShallowLakes monitoring SQL Server database."
        SqlFile.write(GetFileHeader(PURPOSE, GEO_DB_PATH, FEATURE_CLASS, SqlFile.name))

        SqlFile.write("BEGIN TRANSACTION -- COMMIT ROLLBACK\n\n")

        for Row in TrimbleUtility.GetFeatureClassRows(FEATURE_CLASS):
            PySampleDateTime = Row['CreationDateTimeLocal']

            # A record without a creation datetime is not a valid
            # record. End this iteration and go to the next row.
            if PySampleDateTime is None:
                continue

            PondName = str(Row['LakeNum'])
            SampleDate = TrimbleUtility.GetDateTime(PySampleDateTime, 'd')
            GPS_Time = TrimbleUtility.GetDateTime(PySampleDateTime, 't')
            Latitude = str(Row['YCurrentMapCS'])
            Longitude = str(Row['XCurrentMapCS'])
            Depth = str(Row['Depth_in_meters'])

            CommentsDepths = Row['Comment'].strip()

            DataFile = SOURCE_FILE_NAME
            Source = SOURCE_FILE_NAME

            # Validation query
            ValidateQuery = ValidateQuery + "   -- (PondName='" + PondName + "' and  SampleDate = '" + SampleDate + "') Or\n"

            # Ensure the parent Event exists
            EventExistsQuery = EventExistsQuery + " EXISTS  (SELECT PONDNAME FROM tblEvents WHERE Pondname='" + PondName + "' And SampleDate = '" + SampleDate + "') And \n "

            # Write the insert query to file
            CommentStr = (",NULL,'" if CommentsDepths == '' else ",'" + CommentsDepths + "','")
            InsertQueries = (InsertQueries + "      " + SqlPrefix  + "'" + PondName + "','" + SampleDate + "','" + GPS_Time + "'," + Latitude + "," + Longitude + "," + Depth +
                             CommentStr +
                             DataFile + "','" + Source  + "');\n")

        # Write out the query that will determine if the required
        # Events all exist
        EventExistsQuery = EventExistsQuery[:len(EventExistsQuery) - 6] + '\n' # Remove the trailing ' and '

        SqlFile.write(EventExistsQuery + "\n    BEGIN\n    -- Insert the records\n")
        SqlFile.write(InsertQueries)
        SqlFile.write("   END\n")
        SqlFile.write("ELSE\n   Print 'One or more parent Event records related to the record you are trying to insert does not exist.'\n\n")

        SqlFile.write("-- Execute the query below to validate the inserted records.\n-- " + ValidateQuery[:len(ValidateQuery) - 3])

        # Let user know we're done
        FinishedMessage = FEATURE_CLASS + " data written to: " + SqlFile.name + '\n'
        arcpy.AddMessage(FinishedMessage)

    except Exception as e:
        Error = 'Error in function ExportDepthJoined: ' + str(e)
        arcpy.AddMessage(Error)

def ExportLoonsJoined():
    """
    Translates the data in the Loons_Joined featureclass into a script
    of SQL insert queries that can be executed on the AK_ShallowLakes
    database.
    """
    try:
        GEO_DB_PATH = arcpy.env.workspace

        AssertGeoDB(GEO_DB_PATH)

        SOURCE_FILE_NAME = os.path.basename(GEO_DB_PATH) # Extract just the filename from the path.

        FEATURE_CLASS = "Loons_Joined"
        TABLE_NAME = "tblLoons"

        DatetimeStr = TrimbleUtility.GetCurrentDatetimeStr()
        TARGET_FILE_NAME = SOURCE_FILE_NAME + '_' + FEATURE_CLASS + '_Insert_' + DatetimeStr +'.sql'

        SqlFilePath = os.path.dirname(arcpy.env.workspace) + '/' + TARGET_FILE_NAME

        SqlFile = open(SqlFilePath,'a')

        # This will hold the insert queries as they are built
        InsertQueries = ""

        # We need a query to determine if all the Events needed in the
        # new data to be imported exist in tblEvents or not
        EventExistsQuery = "-- Determine if all the necessary parent Event records exist before trying to insert\n"
        EventExistsQuery = EventExistsQuery + "IF\n"

        # We need a query to determine if all the Events needed in the
        # new data to be imported exist in tblEvents or not
        RecordExistsQuery = "    -- Determine if records exist already so we can avoid duplication\n"
        RecordExistsQuery = "        IF "


        # Build a query to select the just inserted records in order
        # to validate them
        ValidateQuery = "SELECT * FROM " + TABLE_NAME + " WHERE\n"

        # Write the header info to file
        PURPOSE = "Transfer loon data from the field Trimble data collection application to the AK_ShallowLakes monitoring SQL Server database."
        SqlFile.write(GetFileHeader(PURPOSE, GEO_DB_PATH, FEATURE_CLASS, SqlFile.name))

        i = 0
        for Row in TrimbleUtility.GetFeatureClassRows(FEATURE_CLASS):
            PySampleDateTime = Row['CreationDateTimeLocal']

            # A record without a creation datetime is not a valid
            # record. End this iteration and go to the next row.
            if PySampleDateTime is None:
                continue

            PondName = str(Row['LakeNum'])
            SampleDate = TrimbleUtility.GetDateTime(PySampleDateTime, 'd')
            Species = str(Row['Loon_Species'])
            NumAdults = str(Row['a___of_Adults'])
            NumYoung = str(Row['a___of_Young'])
            OnWater = str(Row['On_Water_'])

            if OnWater == "Yes":
                VegType = "WATER"
            elif OnWater is None:
                VegType = ""

            DetectionType = str(Row['Identification_Method'])
            Latitude = str(Row['YCurrentMapCS'])
            Longitude = str(Row['XCurrentMapCS'])
            Comments = Row['Loon_Comments'].strip()
            Source = SOURCE_FILE_NAME

            # Validation query
            ValidateQuery = ValidateQuery + "   -- (PondName='" + PondName + "' and SampleDate = '" + SampleDate + "') Or\n"

            # Ensure the parent Event exists
            EventExistsQuery = EventExistsQuery + "    EXISTS  (SELECT PONDNAME FROM tblEvents WHERE Pondname='" + PondName + "' And SampleDate = '" + SampleDate + "') And \n"

            # Ensure the record does not exist already
            RecordExistsQuery = RecordExistsQuery + " NOT EXISTS (SELECT * FROM tblLoons WHERE Pondname='" + PondName + "' And SampleDate = '" + SampleDate  + "') And \n"

            # Write the insert query to file
            CommentStr = (",NULL,'" if Comments == '' else ",'" + Comments + "','")
            VegTypeStr = (",NULL," if VegType == '' else ",'" + VegType + "',")
            InsertQueries = (InsertQueries + "                INSERT INTO " + TABLE_NAME + "(PONDNAME,SAMPLEDATE,SPECIES,NUM_ADULTS,NUM_YOUNG,DETECTION_TYPE,VEG_TYPE,LATITUDE,LONGITUDE,COMMENTS,SOURCE) VALUES("  +
                             "'"  + PondName + "','" + SampleDate + "','" + Species + "'," + NumAdults + "," + NumYoung + ",'" + DetectionType + "'" + VegTypeStr + Latitude + "," + Longitude +
                             CommentStr + Source + "');\n")

            i = i + 1

        SqlFile.write("USE AK_ShallowLakes\n\n")
        SqlFile.write("-- Execute the query below to view/validate records that may be altered.\n-- " + ValidateQuery[:len(ValidateQuery) - 3] + "\n\n")

        # Write out the query that will determine if the required
        # Events all exist
        EventExistsQuery = EventExistsQuery[:len(EventExistsQuery) - 6] + '\n' # Remove the trailing ' and '

        # If the parent Events don't exist in tblEvents then exit the
        # procedure
        SqlFile.write(EventExistsQuery + "    BEGIN\n")
        SqlFile.write("        PRINT 'The required parent Event records exist in tblEvents.'\n")
        SqlFile.write("    " + RecordExistsQuery[:len(RecordExistsQuery) - 6] + "\n\n")
        SqlFile.write("            BEGIN\n")

        # If we get here then the Events exist and the records to be
        # inserted do not exist, insert them.
        SqlFile.write("           -- Danger zone below. ROLLBACK on error.\n")
        SqlFile.write("           -- Insert the records\n")
        SqlFile.write("                PRINT 'inserts'\n")
        SqlFile.write("                BEGIN TRANSACTION -- COMMIT ROLLBACK\n")
        SqlFile.write(InsertQueries)
        SqlFile.write("               PRINT '" + str(i) + " records inserted from " + FEATURE_CLASS + " into database table " + TABLE_NAME + ".'\n")
        SqlFile.write("               PRINT 'DO NOT FORGET TO COMMIT OR ROLLBACK OR THE DATABASE WILL BE LEFT IN A HANGING STATE!!!!'\n")
        SqlFile.write("            END\n")
        SqlFile.write("        ELSE\n")
        SqlFile.write("            PRINT 'One or more records exist already. Uncomment and use the validation query above to help determine which " + FEATURE_CLASS + "\\" + TABLE_NAME + " records exist already.'\n")
        SqlFile.write("    END\n")
        SqlFile.write("ELSE\n    PRINT 'One or more parent Event records (tblEvents) related to the record you are trying to insert does not exist.'\n\n")

        # Let user know we're done
        FinishedMessage = FEATURE_CLASS + " data written to: " + SqlFile.name + '\n'
        arcpy.AddMessage(FinishedMessage)

    except Exception as e:
        Error = 'Error in function ExportLoonsJoined:' + str(e)
        arcpy.AddMessage(Error)

def ExportWaterSampleJoined():
    """
    Translates the data in the Water_Sample_Joined featureclass into a
    script of SQL insert queries that can be executed on the
    AK_ShallowLakes database.
    """
    try:
        GEO_DB_PATH = arcpy.env.workspace

        AssertGeoDB(GEO_DB_PATH)

        SOURCE_FILE_NAME = os.path.basename(GEO_DB_PATH) # Extract just the filename from the path.

        FEATURE_CLASS = "Water_Sample_Joined"
        TABLE_NAME = "tblWaterSamples"

        DatetimeStr = TrimbleUtility.GetCurrentDatetimeStr()
        TARGET_FILE_NAME = SOURCE_FILE_NAME + '_' + FEATURE_CLASS + '_Insert_' + DatetimeStr +'.sql'

        SqlFilePath = os.path.dirname(arcpy.env.workspace) + '/' + TARGET_FILE_NAME

        SqlFile = open(SqlFilePath,'a')

        # Create the first half of the SQL insert query
        SqlPrefix = 'INSERT INTO ' + TABLE_NAME + '([PONDNAME],[SAMPLEDATE],[SAMPLENUMBER],[SAMPLETIME],[SAMPLEDEPTH],[DEPTH],[018_COLL],[SI_DOC_COLL],[IONS_COLL],[TN_TP_COLL],[CHLA_COLL],[NOTES]) VALUES('

        # This will hold the insert queries as they are built
        InsertWaterSamplesQueries = ""

        # We need a query to determine if all the Events needed in the
        # new data to be imported exist in tblEvents or not build up a
        # query to determine this.
        EventExistsQuery = "-- Determine if all the necessary parent Event records exist before trying to insert\nIF\n"

        # Build a query to select the just inserted records in order
        # to validate them
        ValidateQuery = "SELECT * FROM " + TABLE_NAME + " WHERE\n"

        # Write the header info to file
        PURPOSE = "Transfer water sample data from the field Trimble data collection application to the AK_ShallowLakes monitoring SQL Server database."
        SqlFile.write(GetFileHeader(PURPOSE, GEO_DB_PATH, FEATURE_CLASS, SqlFile.name))

        SqlFile.write("BEGIN TRANSACTION -- COMMIT ROLLBACK\n\n")

        for Row in TrimbleUtility.GetFeatureClassRows(FEATURE_CLASS):
            PySampleDateTime = Row['CreationDateTimeLocal']

            # A record without a creation datetime is not a valid
            # record. End this iteration and go to the next row.
            if PySampleDateTime is None:
                continue

            PondName = str(Row['LakeNum'])
            SampleDate = TrimbleUtility.GetDateTime(PySampleDateTime, 'd')
            SampleNumber = str(Row['Sample_Number__A__B__C_']).upper()
            if SampleNumber.strip() == '':
                SampleNumber = 'A'

            SampleTime = TrimbleUtility.GetDateTime(PySampleDateTime, 't')

            if Row['Depth_in_meters'] is not None:
                Depth = str(Row['Depth_in_meters'])
            else:
                Depth = 'NULL'

            SampleDepth = str(0.5)

            Notes = Row['Comment'].strip()

            WaterBottlesCollected = Row['Water_Bottles_Collected_'].strip()
            if WaterBottlesCollected == 'No':
                O18_Coll = '0'
                SI_DOC_Coll = '0'
                IONS_Coll = '0'
                TN_TP_Coll = '0'
                CHLA_Coll = '0'
            elif WaterBottlesCollected == 'Yes':
                O18_Coll = '1'
                SI_DOC_Coll = '1'
                IONS_Coll = '1'
                TN_TP_Coll = '1'
                CHLA_Coll = '1'

            # Validation query
            ValidateQuery = ValidateQuery + "   -- (PondName='" + PondName + "' and  SampleDate = '" + SampleDate + "' and SampleNumber = '" + SampleNumber + "') Or\n"

            # Ensure the parent Event exists
            EventExistsQuery = EventExistsQuery + " EXISTS  (SELECT PONDNAME FROM tblEvents WHERE Pondname='" + PondName + "' And SampleDate = '" + SampleDate + "') And \n "

            # Write the insert query to file
            CommentStr = (",NULL" if Notes == '' else ",'" + Notes + "'")
            InsertWaterSamplesQueries = (InsertWaterSamplesQueries + "INSERT INTO tblWaterSamples([PONDNAME],[SAMPLEDATE],[SAMPLENUMBER],[SAMPLETIME],[SAMPLEDEPTH],[DEPTH],[O18_COLL],[SI_DOC_COLL],[IONS_COLL],[TN_TP_COLL],[CHLA_COLL],[Notes]) VALUES('"  +
                                         PondName + "','" + SampleDate + "','" + SampleNumber + "','" + SampleTime + "'," + SampleDepth + "," + Depth + "," +
                                         O18_Coll + "," + SI_DOC_Coll + "," + IONS_Coll + "," + TN_TP_Coll + "," + CHLA_Coll + CommentStr + ")\n")

        # Write out the query that will determine if the required
        # Events all exist
        EventExistsQuery = EventExistsQuery[:len(EventExistsQuery) - 6] + '\n' # Remove the trailing ' and '

        SqlFile.write(EventExistsQuery + "\n    BEGIN\n    -- Insert the records\n\n")
        SqlFile.write("-- Insert the water samples first\n")
        SqlFile.write(InsertWaterSamplesQueries)
        SqlFile.write("   END\n")
        SqlFile.write("ELSE\n   Print 'One or more parent Event records related to the record you are trying to insert does not exist.'\n\n")

        SqlFile.write("-- Execute the query below to validate the inserted records.\n-- " + ValidateQuery[:len(ValidateQuery) - 3])

        # Let user know we're done
        FinishedMessage = FEATURE_CLASS + " data written to: " + SqlFile.name + '\n'
        arcpy.AddMessage(FinishedMessage)

    except Exception as e:
        Error = 'Error in function ExportWaterSampleJoined: ' + str(e)
        arcpy.AddMessage(Error)

def ExportMonumentJoined():
    """
    Translates the data in the Monument featureclass into a
    script of SQL insert statements that can be executed on the
    AK_ShallowLakes database.
    """
    try:
        GEO_DB_PATH = arcpy.env.workspace

        AssertGeoDB(GEO_DB_PATH)

        SOURCE_FILE_NAME = os.path.basename(GEO_DB_PATH) # Extract just the filename from the path.

        FEATURE_CLASS = "Monument"
        TABLE_NAME = "tblMonuments"

        DatetimeStr = TrimbleUtility.GetCurrentDatetimeStr()
        TARGET_FILE_NAME = SOURCE_FILE_NAME + '_' + FEATURE_CLASS + '_Insert_' + DatetimeStr +'.sql'

        SqlFilePath = os.path.dirname(arcpy.env.workspace) + '/' + TARGET_FILE_NAME

        SqlFile = open(SqlFilePath,'a')

        # Write the header info to file
        PURPOSE = "Transfer monument data from the field Trimble data collection application to the AK_ShallowLakes monitoring SQL Server database.\n"
        SqlFile.write(GetFileHeader(PURPOSE, GEO_DB_PATH, FEATURE_CLASS, SqlFile.name))

        InsertStatements = ''

        for Row in TrimbleUtility.GetFeatureClassRows(FEATURE_CLASS):
            PySampleDateTime = Row['CreationDateTimeLocal']

            PondName = Row['LakeNum']
            MonumentDate = TrimbleUtility.GetDateTime(PySampleDateTime, 'd')
            LatitudeNAD83 = str(Row['YCurrentMapCS'])
            LongitudeNAD83 = str(Row['XCurrentMapCS'])
            Elevation = str(Row['FeatureHeight'])
            LocType = Row['MonType']
            LocMaterial = Row['MonType']

            LocNotes = Row['Location']
            LocNotesStr = (',NULL' if LocNotes.strip() == '' else ",'" + LocNotes + "'")

            LocComments = Row['Comment']
            LocCommentsStr = (',NULL' if LocComments.strip() == '' else ",'" + LocComments + "'")

            AccessType = Row['AccessType']
            GPSType = Row['DeviceType']
            GPSTime = TrimbleUtility.GetDateTime(PySampleDateTime, 't')
            CorrType = Row['CorrStatus']
            EstHError = str(Row['HorizEstAcc'])
            EstVError = str(Row['VertEstAcc'])

            InsertStatements += ('        INSERT INTO ' + TABLE_NAME + ' ' +
                                 '([PONDNAME], [M_DATE], [M_LAT_NAD83], [M_LON_NAD83], [M_ELEVATION], [M_LOC_TYPE], ' +
                                 '[M_LOC_MATERIAL], [M_LOC_NOTES], [M_LOC_COMMENTS], [M_ACCESSTYPE], [M_GPSTYPE], [M_GPSTIME], ' +
                                 '[M_CORR_TYPE], [M_EST_H_ERROR], [M_EST_V_ERROR]) ' +
                                 'VALUES (' +
                                 "'" + PondName + "','" + MonumentDate + "'," + LatitudeNAD83 + "," + LongitudeNAD83 + "," + Elevation + ",'" + LocType +
                                 "','" + LocMaterial + "'" + LocNotesStr + LocCommentsStr + ",'" + AccessType + "','" + GPSType + "','" + GPSTime +
                                 "','" + CorrType + "'," + EstHError + "," + EstVError + ")\n")

        SqlFile.write(WrapSQLStatementsInTransaction(InsertStatements))

    except Exception as e:
        Error = 'Error in function ExportMonumentJoined: ' + str(e)
        arcpy.AddMessage(Error)

def GetFileHeader(Purpose, GeoDBPath, FeatureClass, SQLFileName):
    """
    Standard header information to put in each sql script.
    """
    header = "/*\n"
    header += "NPS Arctic and Central Alaska Inventory and Monitoring Program, Shallow Lakes Monitoring\n"
    header += "This script was generated by the TrimbleGeoDBToDatabase ArcTool available at https://github.com/NPS-ARCN-CAKN/TrimbleGeoDBToDatabase.\n\n"
    header += "Purpose: " + Purpose + "\n"
    header += "Source geodatabase: " + GeoDBPath + "\n"
    header += "FeatureClass: " + FeatureClass  + "\n"
    header += "SQL file name: " + SQLFileName + "\n"
    header += "Script generated by: " + getpass.getuser() + ".\n"
    header += "Date/time: " + str(datetime.datetime.now())  + ".\n"
    header += "*/\n\n"

    return header

def WrapSQLStatementsInTransaction(SQLStatements):
    sql = "BEGIN TRY\n"
    sql += "    BEGIN TRANSACTION\n\n"
    sql += SQLStatements
    sql += "\n     COMMIT TRANSACTION\n"
    sql += "     PRINT N'Successfully inserted ALL records and committed them.'\n"
    sql += "END TRY\n"
    sql += "BEGIN CATCH -- ROLLBACK\n"
    sql += "    IF @@TRANCOUNT > 0\n"
    sql += "    BEGIN\n"
    sql += "        DECLARE @error_msg NVARCHAR(MAX)\n"
    sql += "        SELECT @error_msg = ERROR_MESSAGE()\n"
    sql += "        PRINT N'Error: ' + @error_msg + char(13) + char(10) + char(13) + char(10)\n"
    sql += "        ROLLBACK TRANSACTION\n"
    sql += "        PRINT N'Rolling back transaction; NO records have been inserted.'\n"
    sql += "    END\n"
    sql += "END CATCH\n\n"

    return sql

def AssertGeoDB(GEO_DB_PATH):
    assert GEO_DB_PATH is not None, "arcpy.env.workspace must be a geodatabase path string!"
