-- Initialize MySQL database for Padel Backend
CREATE DATABASE IF NOT EXISTS padel_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'padel_user'@'%' IDENTIFIED BY 'padel_password';
GRANT ALL PRIVILEGES ON padel_db.* TO 'padel_user'@'%';
GRANT ALL PRIVILEGES ON padel_db.* TO 'root'@'%';
FLUSH PRIVILEGES;
USE padel_db;
SET SESSION sql_mode = 'TRADITIONAL';
