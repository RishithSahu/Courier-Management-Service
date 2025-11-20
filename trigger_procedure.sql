-- db_scripts.sql
-- SQL schema, procedures, functions, views, triggers and sample data for Courier Management System
-- Run with: mysql -u <user> -p courierdb < db_scripts.sql

-- Drop objects if they exist (safe to re-run)
DROP TRIGGER IF EXISTS trg_payments_after_insert;
DROP TRIGGER IF EXISTS trg_courier_after_update_agent;
DROP PROCEDURE IF EXISTS sp_mark_payment_completed;
DROP PROCEDURE IF EXISTS sp_assign_agent;
DROP FUNCTION IF EXISTS fn_payment_status;
DROP FUNCTION IF EXISTS fn_last_tracking_status;
DROP VIEW IF EXISTS vw_courier_summary;
DROP VIEW IF EXISTS vw_agent_assignments;

-- TABLES
CREATE TABLE IF NOT EXISTS `Admin` (
  `aid` INT PRIMARY KEY AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `name` VARCHAR(255),
  `phoneno` VARCHAR(50)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `User` (
  `uid` INT PRIMARY KEY AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `name` VARCHAR(255),
  `phoneno` VARCHAR(50),
  `aid` INT,
  FOREIGN KEY (aid) REFERENCES Admin(aid) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Credentials` (
  `email` VARCHAR(255) PRIMARY KEY,
  `password` VARCHAR(255) NOT NULL,
  `role` ENUM('User','Admin') NOT NULL,
  `uid` INT,
  `aid` INT,
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE SET NULL,
  FOREIGN KEY (aid) REFERENCES Admin(aid) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Delivery_agent` (
  `agentid` INT PRIMARY KEY AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `phone` VARCHAR(50),
  `assigned_area` VARCHAR(255)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Courier_pricing` (
  `priceid` INT PRIMARY KEY AUTO_INCREMENT,
  `courier_type` ENUM('Domestic','International') NOT NULL,
  `min_weight` DECIMAL(5,2) DEFAULT 0.00,
  `max_weight` DECIMAL(5,2) DEFAULT 0.00,
  `base_price` DECIMAL(10,2) NOT NULL,
  `price_per_km` DECIMAL(10,2) NOT NULL,
  `aid` INT,
  FOREIGN KEY (aid) REFERENCES Admin(aid) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Courier` (
  `cid` INT PRIMARY KEY AUTO_INCREMENT,
  `uid` INT,
  `semail` VARCHAR(255) NOT NULL,
  `remail` VARCHAR(255) NOT NULL,
  `sname` VARCHAR(255) NOT NULL,
  `rname` VARCHAR(255) NOT NULL,
  `sphone` VARCHAR(50) NOT NULL,
  `rphone` VARCHAR(50) NOT NULL,
  `saddress` VARCHAR(255) NOT NULL,
  `raddress` VARCHAR(255) NOT NULL,
  `weight` DECIMAL(5,2) NOT NULL,
  `billno` BIGINT NOT NULL UNIQUE,
  `courier_type` ENUM('Domestic','International') DEFAULT 'Domestic',
  `country` VARCHAR(100) DEFAULT 'India',
  `date` DATE NOT NULL,
  `agentid` INT,
  `priceid` INT,
  FOREIGN KEY (uid) REFERENCES `User`(uid) ON DELETE SET NULL,
  FOREIGN KEY (agentid) REFERENCES Delivery_agent(agentid) ON DELETE SET NULL,
  FOREIGN KEY (priceid) REFERENCES Courier_pricing(priceid) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Courier_tracking` (
  `trackid` INT PRIMARY KEY AUTO_INCREMENT,
  `cid` INT NOT NULL,
  `status` VARCHAR(100) NOT NULL,
  `current_location` VARCHAR(255),
  `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (cid) REFERENCES Courier(cid) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Payments` (
  `pid` INT PRIMARY KEY AUTO_INCREMENT,
  `cid` INT NOT NULL,
  `uid` INT NOT NULL,
  `amount` DECIMAL(10,2) NOT NULL,
  `payment_mode` ENUM('Credit Card','Debit Card','UPI','Net Banking','Cash on Delivery'),
  `payment_status` ENUM('Pending','Completed','Failed') DEFAULT 'Pending',
  `transaction_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (cid) REFERENCES Courier(cid) ON DELETE CASCADE,
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `Notification_config` (
  `id` INT PRIMARY KEY AUTO_INCREMENT,
  `smtp_server` VARCHAR(255),
  `smtp_port` INT,
  `smtp_username` VARCHAR(255),
  `smtp_password` TEXT,
  `smtp_use_tls` BOOLEAN DEFAULT TRUE,
  `email_from` VARCHAR(255),
  `twilio_account_sid` VARCHAR(255),
  `twilio_auth_token` TEXT,
  `twilio_from_number` VARCHAR(50)
) ENGINE=InnoDB;

-- VIEWS
CREATE OR REPLACE VIEW vw_courier_summary AS
SELECT c.cid, c.billno, c.sname, c.rname, p.amount, p.payment_status,
  (SELECT ct.status FROM Courier_tracking ct WHERE ct.cid = c.cid ORDER BY ct.updated_at DESC LIMIT 1) AS last_status,
  c.agentid
FROM Courier c
LEFT JOIN Payments p ON p.cid = c.cid;

CREATE OR REPLACE VIEW vw_agent_assignments AS
SELECT a.agentid, a.name AS agent_name, a.email AS agent_email, COUNT(c.cid) AS assigned_count
FROM Delivery_agent a
LEFT JOIN Courier c ON c.agentid = a.agentid
GROUP BY a.agentid, a.name, a.email;

-- PROCEDURES and FUNCTIONS
DELIMITER $$
CREATE PROCEDURE sp_mark_payment_completed(IN p_cid INT)
BEGIN
  -- Mark payments completed for this courier
  UPDATE Payments SET payment_status='Completed', transaction_date=NOW() WHERE cid = p_cid;

  -- Insert a tracking row if latest isn't 'Payment Received' (avoid duplicates)
  DECLARE last_status VARCHAR(100);
  DECLARE last_time DATETIME;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET last_status = NULL, last_time = NULL;

  SELECT status, updated_at INTO last_status, last_time
    FROM Courier_tracking WHERE cid = p_cid ORDER BY updated_at DESC LIMIT 1;

  IF last_status IS NULL OR last_status <> 'Payment Received' OR (last_time IS NOT NULL AND TIMESTAMPDIFF(SECOND, last_time, NOW()) > 120) THEN
    INSERT INTO Courier_tracking (cid, status, current_location, updated_at)
    VALUES (p_cid, 'Payment Received', 'Billing', NOW());
  END IF;
END$$

CREATE PROCEDURE sp_assign_agent(IN p_cid INT, IN p_agentid INT)
BEGIN
  DECLARE old_agent INT;
  SELECT agentid INTO old_agent FROM Courier WHERE cid = p_cid LIMIT 1;
  IF old_agent IS NULL OR old_agent != p_agentid THEN
    UPDATE Courier SET agentid = p_agentid WHERE cid = p_cid;
    INSERT INTO Courier_tracking (cid, status, current_location, updated_at)
    VALUES (p_cid, 'Assigned to Agent', 'Local Delivery Hub', NOW());
  END IF;
END$$

CREATE FUNCTION fn_payment_status(p_cid INT) RETURNS VARCHAR(20) DETERMINISTIC
BEGIN
  DECLARE pstat VARCHAR(20);
  SELECT payment_status INTO pstat FROM Payments WHERE cid = p_cid LIMIT 1;
  IF pstat IS NULL THEN
    RETURN 'Unknown';
  END IF;
  RETURN pstat;
END$$

CREATE FUNCTION fn_last_tracking_status(p_cid INT) RETURNS VARCHAR(100) DETERMINISTIC
BEGIN
  DECLARE last_status VARCHAR(100);
  SELECT status INTO last_status FROM Courier_tracking WHERE cid = p_cid ORDER BY updated_at DESC LIMIT 1;
  IF last_status IS NULL THEN
    RETURN 'No Status';
  END IF;
  RETURN last_status;
END$$
DELIMITER ;

-- TRIGGERS
DELIMITER $$
CREATE TRIGGER trg_payments_after_insert
AFTER INSERT ON Payments
FOR EACH ROW
BEGIN
  DECLARE last_status VARCHAR(100);
  DECLARE last_time DATETIME;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET last_status = NULL, last_time = NULL;

  IF NEW.payment_status = 'Completed' THEN
    SELECT status, updated_at INTO last_status, last_time
      FROM Courier_tracking WHERE cid = NEW.cid ORDER BY updated_at DESC LIMIT 1;

    IF last_status IS NULL OR last_status <> 'Payment Received' OR (last_time IS NOT NULL AND TIMESTAMPDIFF(SECOND, last_time, NOW()) > 120) THEN
      INSERT INTO Courier_tracking (cid, status, current_location, updated_at)
      VALUES (NEW.cid, 'Payment Received', 'Billing', NOW());
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_courier_after_update_agent
AFTER UPDATE ON Courier
FOR EACH ROW
BEGIN
  DECLARE last_status VARCHAR(100);
  DECLARE last_time DATETIME;
  DECLARE action_status VARCHAR(100);
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET last_status = NULL, last_time = NULL;

  IF NOT (OLD.agentid <=> NEW.agentid) THEN
    IF NEW.agentid IS NULL THEN
      SET action_status = 'Agent Unassigned';
    ELSE
      SET action_status = 'Assigned to Agent';
    END IF;

    SELECT status, updated_at INTO last_status, last_time
      FROM Courier_tracking WHERE cid = NEW.cid ORDER BY updated_at DESC LIMIT 1;

    IF last_status IS NULL OR last_status <> action_status OR (last_time IS NOT NULL AND TIMESTAMPDIFF(SECOND, last_time, NOW()) > 120) THEN
      INSERT INTO Courier_tracking (cid, status, current_location, updated_at)
      VALUES (NEW.cid, action_status, 'Local Delivery Hub', NOW());
    END IF;
  END IF;
END$$
DELIMITER ;

-- SAMPLE DATA (optional, uncomment and adjust IDs if needed)
-- INSERT INTO Delivery_agent (name, email, phone, assigned_area) VALUES ('Agent One','agent1@example.com','+911234567890','Zone A');
-- INSERT INTO Courier_pricing (courier_type, min_weight, max_weight, base_price, price_per_km) VALUES ('Domestic',0.00,1.00,50.00,2.00);

-- END of db_scripts.sql
