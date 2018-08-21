CREATE USER 'saq-user'@'localhost' IDENTIFIED BY 'SAQ_USER_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON `saq-production`.* TO 'saq-user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `ace-workload`.* TO 'saq-user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `brocess`.* TO 'saq-user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `chronos`.* TO 'saq-user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `email-archive`.* TO 'saq-user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `hal9000`.* TO 'saq-user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON `cloudphish`.* TO 'saq-user'@'localhost';
FLUSH PRIVILEGES;
