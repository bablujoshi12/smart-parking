-- ========================================================================
--                    SMART PARKING SYSTEM - DATABASE SETUP
-- ========================================================================
-- Database Name: smartparking
-- Password: bablu@123456
-- ========================================================================

CREATE DATABASE IF NOT EXISTS smartparking;
USE smartparking;

-- ========================================================================
--                                TABLES
-- ========================================================================

CREATE TABLE `parking` (
  `Cell_id` int NOT NULL AUTO_INCREMENT,
  `Cell_Name` varchar(20) DEFAULT NULL,
  `Status` tinyint DEFAULT NULL,
  PRIMARY KEY (`Cell_id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `reserve` (
  `Resid` int NOT NULL AUTO_INCREMENT,
  `Cell_id` int DEFAULT NULL,
  `VehNo` varchar(20) DEFAULT NULL,
  `InTime` datetime DEFAULT NULL,
  `OutTime` datetime DEFAULT NULL,
  `MobNo` varchar(12) DEFAULT NULL,
  `enStat` tinyint DEFAULT '1',
  `exStat` tinyint DEFAULT '1',
  PRIMARY KEY (`Resid`),
  KEY `reserve_ibfk_1` (`Cell_id`),
  CONSTRAINT `reserve_ibfk_1` FOREIGN KEY (`Cell_id`) REFERENCES `parking` (`Cell_id`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `chk_entry_status` CHECK ((`enStat` between 1 and 3)),
  CONSTRAINT `chk_exit_status` CHECK ((`exStat` between 1 and 3))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `parkingrates` (
  `Rate_id` int NOT NULL AUTO_INCREMENT,
  `Pid` int DEFAULT NULL,
  `Stay_Time` int DEFAULT NULL,
  `Rate` float DEFAULT NULL,
  PRIMARY KEY (`Rate_id`),
  KEY `Pid` (`Pid`),
  CONSTRAINT `parkingrates_ibfk_1` FOREIGN KEY (`Pid`) REFERENCES `parking` (`Cell_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ========================================================================
--                            STORED PROCEDURES
-- ========================================================================

DELIMITER $$

-- Procedure: UpdateParkingExitStatus
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateParkingExitStatus`(IN resID INT)
BEGIN
	UPDATE smartparking.reserve SET exStat=3 WHERE Resid = resID AND exStat=2 ORDER BY OutTime DESC LIMIT 1;
END$$

-- Procedure: UpdateEntryStatus
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateEntryStatus`(IN resID INT, IN statusEntry TINYINT)
BEGIN
	UPDATE reserve SET enStat = statusEntry WHERE Resid = resID;
END$$

-- Procedure: ReserveCellToVehicle
CREATE DEFINER=`root`@`localhost` PROCEDURE `ReserveCellToVehicle`(
    IN VehicleNumber VARCHAR(20),
    IN MobileNumber BIGINT
)
BEGIN
    DECLARE CellID INT;
    DECLARE vacantCells INT;
    DECLARE sql_error_code INT;
    DECLARE sql_error_message TEXT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION 
    BEGIN
        ROLLBACK;
        GET DIAGNOSTICS CONDITION 1 
            sql_error_code = MYSQL_ERRNO, 
            sql_error_message = MESSAGE_TEXT;
        SELECT CONCAT('Error Code: ', sql_error_code, 
                      ', Message: ', sql_error_message) AS ErrorDetails;
    END;

    START TRANSACTION;
   
    -- Step 1: Get the first available cell
    SELECT MIN(Cell_id) INTO CellID 
    FROM parking 
    WHERE Status = 0
    FOR UPDATE;
    
    -- Step 2: Handle if no cell is available
    IF CellID IS NULL THEN
        ROLLBACK;
        SELECT 'No Vacant Cell.' AS Message;
    ELSE
        -- Step 3: Reserve the cell
        INSERT INTO Reserve (Cell_id, VehNo, InTime, OutTime, MobNo) 
        VALUES (CellID, VehicleNumber, NOW(), NULL, MobileNumber);
        
        -- Step 4: Mark the cell as occupied
        UPDATE parking 
        SET Status = 1 
        WHERE Cell_id = CellID;
        
        -- Step 5: Count remaining vacant cells
        SELECT COUNT(Cell_id) INTO vacantCells 
        FROM smartparking.parking 
        WHERE Status = 0;

        COMMIT;
        
        -- Step 6: Return reservation details along with vacantCells
        SELECT 
            r.Cell_id AS cellID,
            p.Cell_Name AS cellName,
            r.VehNo AS vehNo,
            vacantCells AS vacantCells
        FROM Reserve r
        INNER JOIN parking p ON r.Cell_id = p.Cell_id
        ORDER BY r.Resid DESC
        LIMIT 1;
    END IF;
END$$

-- Procedure: GetParkingExitStatus
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetParkingExitStatus`()
BEGIN
	SELECT Resid AS res_id, Cell_id AS cell_id, exStat AS exit_status 
    FROM smartparking.reserve WHERE exStat=2 ORDER BY OutTime DESC LIMIT 1;
END$$

-- Procedure: GetParkingAllotmentStatus
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetParkingAllotmentStatus`()
BEGIN
    DECLARE CellID INT;
    DECLARE vacantCells INT;
    DECLARE sql_error_code INT;
    DECLARE sql_error_message TEXT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION 
    BEGIN
        ROLLBACK;
        GET DIAGNOSTICS CONDITION 1 
            sql_error_code = MYSQL_ERRNO, 
            sql_error_message = MESSAGE_TEXT;
        SELECT CONCAT('Error Code: ', sql_error_code, 
                      ', Message: ', sql_error_message) AS ErrorDetails;
    END;

	SELECT COUNT(Cell_id) INTO vacantCells 
        FROM smartparking.parking 
        WHERE Status = 0;

    SELECT
		r.Resid AS res_id,
		r.Cell_id AS cell_id,
		p.Cell_Name AS cell_name,
		r.VehNo AS veh_no,
		vacantCells AS vacant_cells,
        r.enStat AS entry_status
	FROM Reserve r
	INNER JOIN parking p ON r.Cell_id = p.Cell_id
	ORDER BY r.Resid DESC
	LIMIT 1;
END$$

-- Procedure: CheckAlreadyRegistered
CREATE DEFINER=`root`@`localhost` PROCEDURE `CheckAlreadyRegistered`(IN MobileNumber BIGINT)
BEGIN
    DECLARE sql_error_code INT;
    DECLARE sql_error_message TEXT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION 
    BEGIN
        ROLLBACK;
        GET DIAGNOSTICS CONDITION 1 
            sql_error_code = MYSQL_ERRNO, 
            sql_error_message = MESSAGE_TEXT;
        SELECT CONCAT('Error Code: ', sql_error_code, 
                      ', Message: ', sql_error_message) AS ErrorDetails;
    END;
    
	SELECT parking.Cell_Name, reserve.VehNo
	FROM reserve
	INNER JOIN parking ON reserve.Cell_id = parking.Cell_id
	WHERE reserve.OutTime IS NULL
	AND reserve.MobNo = MobileNumber;
END$$

DELIMITER ;

-- ========================================================================
--                            SAMPLE DATA (Optional)
-- ========================================================================

-- Insert sample parking cells
INSERT INTO parking (Cell_Name, Status) VALUES
('A1', 0), ('A2', 0), ('A3', 0), ('A4', 0), ('A5', 0),
('B1', 0), ('B2', 0), ('B3', 0), ('B4', 0), ('B5', 0),
('C1', 0), ('C2', 0), ('C3', 0), ('C4', 0), ('C5', 0),
('D1', 0), ('D2', 0), ('D3', 0), ('D4', 0), ('D5', 0);

-- ========================================================================
--                            VERIFICATION
-- ========================================================================

-- Verify tables
SELECT 'Tables Created' AS Status;
SHOW TABLES;

-- Verify procedures
SELECT 'Stored Procedures' AS Type, ROUTINE_NAME AS Name 
FROM INFORMATION_SCHEMA.ROUTINES 
WHERE ROUTINE_SCHEMA = 'smartparking' AND ROUTINE_TYPE = 'PROCEDURE';

-- Verify parking cells
SELECT COUNT(*) AS TotalCells FROM parking;
SELECT COUNT(*) AS VacantCells FROM parking WHERE Status = 0;

