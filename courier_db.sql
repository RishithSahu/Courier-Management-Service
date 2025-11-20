-- --------------------------------------------------------
-- Courier Management System Database
-- Version 4.1 (Full data with 10+ dummy rows per table)
-- --------------------------------------------------------

-- Initial Setup
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

-- Create and Use Database
CREATE DATABASE IF NOT EXISTS courierdb
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
USE courierdb;

-- --------------------------------------------------------
-- Table Structures (Dropping existing tables to prevent errors on re-run)
-- --------------------------------------------------------

DROP TABLE IF EXISTS Feedback, Payments, Courier_tracking, Contact, Courier, Courier_pricing, Delivery_agent, Credentials, User, Admin;

CREATE TABLE Admin (
  aid INT(11) NOT NULL AUTO_INCREMENT,
  email VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(50) DEFAULT NULL,
  phoneno VARCHAR(20) DEFAULT NULL,
  PRIMARY KEY (aid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE User (
  uid INT(11) NOT NULL AUTO_INCREMENT,
  email VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(50) DEFAULT NULL,
  phoneno VARCHAR(20) DEFAULT NULL,
  aid INT(11) DEFAULT NULL,
  PRIMARY KEY (uid),
  FOREIGN KEY (aid) REFERENCES Admin(aid) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Credentials (
  email VARCHAR(50) NOT NULL,
  password VARCHAR(255) NOT NULL,
  role ENUM('User', 'Admin') NOT NULL,
  uid INT(11) DEFAULT NULL,
  aid INT(11) DEFAULT NULL,
  PRIMARY KEY (email),
  UNIQUE KEY (uid),
  UNIQUE KEY (aid),
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE CASCADE,
  FOREIGN KEY (aid) REFERENCES Admin(aid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Delivery_agent (
  agentid INT AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,
  email VARCHAR(50) NOT NULL UNIQUE,
  phone VARCHAR(20) DEFAULT NULL,
  assigned_area VARCHAR(100) DEFAULT NULL,
  PRIMARY KEY (agentid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Courier_pricing (
  priceid INT AUTO_INCREMENT,
  courier_type ENUM('Domestic', 'International') NOT NULL,
  min_weight DECIMAL(5,2) DEFAULT 0.00,
  max_weight DECIMAL(5,2) DEFAULT 0.00,
  base_price DECIMAL(10,2) NOT NULL,
  price_per_km DECIMAL(10,2) NOT NULL,
  aid INT(11) DEFAULT NULL,
  PRIMARY KEY (priceid),
  FOREIGN KEY (aid) REFERENCES Admin(aid) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Courier (
  cid INT(11) NOT NULL AUTO_INCREMENT,
  uid INT(11) DEFAULT NULL,
  semail VARCHAR(50) NOT NULL,
  remail VARCHAR(50) NOT NULL,
  sname VARCHAR(50) NOT NULL,
  rname VARCHAR(50) NOT NULL,
  sphone VARCHAR(20) NOT NULL,
  rphone VARCHAR(20) NOT NULL,
  saddress VARCHAR(100) NOT NULL,
  raddress VARCHAR(100) NOT NULL,
  weight DECIMAL(5,2) NOT NULL,
  billno INT(11) NOT NULL UNIQUE,
  courier_type ENUM('Domestic','International') DEFAULT 'Domestic',
  country VARCHAR(50) DEFAULT 'India',
  image TEXT DEFAULT NULL,
  date DATE NOT NULL,
  agentid INT(11) DEFAULT NULL,
  priceid INT(11) DEFAULT NULL,
  PRIMARY KEY (cid),
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE CASCADE,
  FOREIGN KEY (agentid) REFERENCES Delivery_agent(agentid) ON DELETE SET NULL,
  FOREIGN KEY (priceid) REFERENCES Courier_pricing(priceid) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Contact (
  id INT(11) NOT NULL AUTO_INCREMENT,
  email VARCHAR(50) NOT NULL,
  title VARCHAR(50) NOT NULL,
  comment VARCHAR(300) NOT NULL,
  date DATE DEFAULT (CURRENT_DATE),
  uid INT(11) DEFAULT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Courier_tracking (
  trackid INT AUTO_INCREMENT,
  cid INT NOT NULL,
  status VARCHAR(50) NOT NULL,
  current_location VARCHAR(100) DEFAULT NULL,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (trackid),
  FOREIGN KEY (cid) REFERENCES Courier(cid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Payments (
  pid INT AUTO_INCREMENT,
  cid INT NOT NULL,
  uid INT NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  payment_mode ENUM('Credit Card', 'Debit Card', 'UPI', 'Net Banking', 'Cash on Delivery'),
  payment_status ENUM('Pending', 'Completed', 'Failed') DEFAULT 'Pending',
  transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (pid),
  FOREIGN KEY (cid) REFERENCES Courier(cid) ON DELETE CASCADE,
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE Feedback (
  fid INT AUTO_INCREMENT,
  uid INT DEFAULT NULL,
  cid INT NOT NULL,
  comment TEXT,
  date DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (fid),
  FOREIGN KEY (uid) REFERENCES User(uid) ON DELETE SET NULL,
  FOREIGN KEY (cid) REFERENCES Courier(cid) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- Dummy Data Inserts (10+ rows per table)
-- --------------------------------------------------------

-- Admin
INSERT INTO Admin (email, name, phoneno) VALUES
('admin1@courier.com', 'Rajesh Kumar', '9999999901'),
('admin2@courier.com', 'Sunita Sharma', '9999999902'),
('admin3@courier.com', 'Amit Patel', '9999999903'),
('admin4@courier.com', 'Priya Singh', '9999999904'),
('admin5@courier.com', 'Vikram Rathod', '9999999905'),
('admin6@courier.com', 'Anjali Mehta', '9999999906'),
('admin7@courier.com', 'Sanjay Verma', '9999999907'),
('admin8@courier.com', 'Deepika Nair', '9999999908'),
('admin9@courier.com', 'Arun Joshi', '9999999909'),
('admin10@courier.com', 'Kavita Iyer', '9999999910');

-- User
INSERT INTO User (email, name, phoneno, aid) VALUES
('alice@example.com', 'Alice', '9876543210', 1),
('bob@example.com', 'Bob', '9876543211', 2),
('charlie@example.com', 'Charlie', '9876543212', 3),
('diana@example.com', 'Diana', '9876543213', 4),
('evan@example.com', 'Evan', '9876543214', 5),
('fiona@example.com', 'Fiona', '9876543215', 6),
('george@example.com', 'George', '9876543216', 7),
('hannah@example.com', 'Hannah', '9876543217', 8),
('ian@example.com', 'Ian', '9876543218', 9),
('julia@example.com', 'Julia', '9876543219', 10);

-- Credentials (Passwords are for example only. USE HASHED VALUES in production)
INSERT INTO Credentials (email, password, role, uid, aid) VALUES
('admin1@courier.com', 'adminpass1', 'Admin', NULL, 1),
('admin2@courier.com', 'adminpass2', 'Admin', NULL, 2),
('admin3@courier.com', 'adminpass3', 'Admin', NULL, 3),
('admin4@courier.com', 'adminpass4', 'Admin', NULL, 4),
('admin5@courier.com', 'adminpass5', 'Admin', NULL, 5),
('admin6@courier.com', 'adminpass6', 'Admin', NULL, 6),
('admin7@courier.com', 'adminpass7', 'Admin', NULL, 7),
('admin8@courier.com', 'adminpass8', 'Admin', NULL, 8),
('admin9@courier.com', 'adminpass9', 'Admin', NULL, 9),
('admin10@courier.com', 'adminpass10', 'Admin', NULL, 10),
('alice@example.com', 'userpass1', 'User', 1, NULL),
('bob@example.com', 'userpass2', 'User', 2, NULL),
('charlie@example.com', 'userpass3', 'User', 3, NULL),
('diana@example.com', 'userpass4', 'User', 4, NULL),
('evan@example.com', 'userpass5', 'User', 5, NULL),
('fiona@example.com', 'userpass6', 'User', 6, NULL),
('george@example.com', 'userpass7', 'User', 7, NULL),
('hannah@example.com', 'userpass8', 'User', 8, NULL),
('ian@example.com', 'userpass9', 'User', 9, NULL),
('julia@example.com', 'userpass10', 'User', 10, NULL);

-- Delivery_agent
INSERT INTO Delivery_agent (name, email, phone, assigned_area) VALUES
('Ravi Kumar', 'ravi@d-agent.com', '9876501234', 'Bangalore'),
('Priya Sharma', 'priya@d-agent.com', '9855501234', 'Chennai'),
('David Miller', 'david@d-agent.com', '9823405678', 'USA'),
('Anita Rao', 'anita@d-agent.com', '9812345678', 'Hyderabad'),
('John Smith', 'john@d-agent.com', '9801122334', 'Mumbai'),
('Sara Khan', 'sara@d-agent.com', '9898989898', 'Delhi'),
('Ramesh Patel', 'ramesh@d-agent.com', '9898001234', 'Ahmedabad'),
('Mary Thomas', 'mary@d-agent.com', '9811122233', 'Pune'),
('Steve Wilson', 'steve@d-agent.com', '9776655443', 'London'),
('Tom Lee', 'tom@d-agent.com', '9665544332', 'New York');

-- Courier_pricing
INSERT INTO Courier_pricing (courier_type, min_weight, max_weight, base_price, price_per_km, aid) VALUES
('Domestic', 0.01, 1.00, 50.00, 5.00, 1),
('Domestic', 1.01, 5.00, 100.00, 8.00, 2),
('Domestic', 5.01, 10.00, 150.00, 10.00, 3),
('Domestic', 10.01, 20.00, 250.00, 12.00, 4),
('International', 0.01, 1.00, 500.00, 50.00, 5),
('International', 1.01, 5.00, 1000.00, 75.00, 6),
('International', 5.01, 10.00, 1800.00, 90.00, 7),
('International', 10.01, 20.00, 3000.00, 120.00, 8),
('Domestic', 20.01, 50.00, 500.00, 15.00, 9),
('International', 20.01, 50.00, 5000.00, 150.00, 10);

-- Courier
INSERT INTO Courier (uid, semail, remail, sname, rname, sphone, rphone, saddress, raddress, weight, billno, courier_type, country, date, agentid, priceid) VALUES
(1, 'alice@example.com', 'rec1@other.com', 'Alice', 'Receiver One', '9876543210', '9988776601', 'Mumbai', 'Chennai', 0.5, 1001, 'Domestic', 'India', '2025-10-01', 1, 1),
(2, 'bob@example.com', 'rec2@other.com', 'Bob', 'Receiver Two', '9876543211', '9988776602', 'Delhi', 'Bangalore', 2.0, 1002, 'Domestic', 'India', '2025-10-02', 2, 2),
(3, 'charlie@example.com', 'rec3@other.com', 'Charlie', 'Receiver Three', '9876543212', '9988776603', 'Hyderabad', 'London', 4.5, 1003, 'International', 'UK', '2025-10-03', 9, 6),
(4, 'diana@example.com', 'rec4@other.com', 'Diana', 'Receiver Four', '9876543213', '9988776604', 'Pune', 'New York', 8.0, 1004, 'International', 'USA', '2025-10-04', 10, 7),
(5, 'evan@example.com', 'rec5@other.com', 'Evan', 'Receiver Five', '9876543214', '9988776605', 'Ahmedabad', 'Kolkata', 12.0, 1005, 'Domestic', 'India', '2025-10-05', 7, 4),
(6, 'fiona@example.com', 'rec6@other.com', 'Fiona', 'Receiver Six', '9876543215', '9988776606', 'Jaipur', 'Sydney', 18.5, 1006, 'International', 'Australia', '2025-10-06', 3, 8),
(7, 'george@example.com', 'rec7@other.com', 'George', 'Receiver Seven', '9876543216', '9988776607', 'Lucknow', 'Goa', 25.0, 1007, 'Domestic', 'India', '2025-10-07', 8, 9),
(8, 'hannah@example.com', 'rec8@other.com', 'Hannah', 'Receiver Eight', '9876543217', '9988776608', 'Chandigarh', 'Dubai', 30.0, 1008, 'International', 'UAE', '2025-10-08', 3, 10),
(9, 'ian@example.com', 'rec9@other.com', 'Ian', 'Receiver Nine', '9876543218', '9988776609', 'Indore', 'Bhopal', 6.0, 1009, 'Domestic', 'India', '2025-10-09', 4, 3),
(10, 'julia@example.com', 'rec10@other.com', 'Julia', 'Receiver Ten', '9876543219', '9988776610', 'Nagpur', 'Surat', 0.8, 1010, 'Domestic', 'India', '2025-10-10', 5, 1);

-- Contact
INSERT INTO Contact (email, title, comment, uid) VALUES
('alice@example.com', 'Query about international shipping', 'What are the charges for shipping to Canada?', 1),
('bob@example.com', 'Complaint: Late Delivery', 'My package (Bill #1002) was supposed to arrive yesterday.', 2),
('charlie@example.com', 'Feedback: Great Service', 'The delivery agent was very professional. Thank you!', 3),
('diana@example.com', 'Question about packaging', 'Do you provide packaging services for fragile items?', 4),
('evan@example.com', 'Issue with tracking', 'The tracking information has not updated in 3 days.', 5),
('fiona@example.com', 'Request for bulk pricing', 'We are a small business and need to ship 50+ parcels a month.', 6),
('george@example.com', 'Address Change Request', 'Can I change the delivery address for my package?', 7),
('hannah@example.com', 'Payment Failed', 'My payment failed but the amount was debited from my account.', 8),
('ian@example.com', 'Lost Item Claim', 'I believe my package has been lost in transit.', 9),
('julia@example.com', 'General Inquiry', 'What are your operational hours during the holidays?', 10);

-- Courier_tracking
INSERT INTO Courier_tracking (cid, status, current_location) VALUES
(1, 'Delivered', 'Chennai'),
(2, 'Out for Delivery', 'Bangalore'),
(3, 'In Transit', 'London Heathrow Airport'),
(4, 'Customs Clearance', 'JFK Airport, New York'),
(5, 'In Transit', 'Kolkata Hub'),
(6, 'Dispatched', 'Sydney Sorting Center'),
(7, 'Delivered', 'Goa'),
(8, 'At Hub', 'Dubai International Airport'),
(9, 'Picked Up', 'Indore'),
(10, 'At Hub', 'Nagpur');

-- Payments
INSERT INTO Payments (cid, uid, amount, payment_mode, payment_status) VALUES
(1, 1, 60.00, 'UPI', 'Completed'),
(2, 2, 110.00, 'Credit Card', 'Completed'),
(3, 3, 1500.00, 'Net Banking', 'Completed'),
(4, 4, 2500.00, 'Debit Card', 'Completed'),
(5, 5, 275.00, 'UPI', 'Pending'),
(6, 6, 4500.00, 'Credit Card', 'Completed'),
(7, 7, 550.00, 'Cash on Delivery', 'Completed'),
(8, 8, 6000.00, 'Net Banking', 'Failed'),
(9, 9, 160.00, 'UPI', 'Completed'),
(10, 10, 55.00, 'Debit Card', 'Completed');

-- Feedback
INSERT INTO Feedback (uid, cid, comment) VALUES
(1, 1, 'Very fast and reliable service. The package was in perfect condition.'),
(2, 2, 'The delivery person was polite and followed the instructions.'),
(3, 3, 'International shipping was smoother than I expected.'),
(4, 4, 'Excellent customer support helped me with a query.'),
(5, 5, 'Tracking updates could be more frequent.'),
(6, 6, 'A bit expensive, but the service quality is worth it.'),
(7, 7, 'Delivered on time. Happy with the service.'),
(8, 8, 'My previous issue was resolved quickly. Thanks to the support team.'),
(9, 9, 'Good, standard service. No complaints.'),
(10, 10, 'The website is very easy to use for booking a courier.');

-- Commit Transaction
COMMIT;