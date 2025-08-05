import java.io.FileWriter; import java.io.IOException; import java.sql.Connection; import java.sql.DriverManager; import java.sql.ResultSet; import java.sql.ResultSetMetaData; import java.sql.SQLException; import java.sql.Statement;

public class QueryToCSVExporter { public static void main(String[] args) { String url = "jdbc:mysql://localhost:3306/your_database"; // Change as needed String user = "your_username"; String password = "your_password"; String query = "SELECT * FROM your_table"; // Change to your dynamic query String csvFilePath = "output.csv";

exportQueryResultToCSV(url, user, password, query, csvFilePath);
}

public static void exportQueryResultToCSV(String url, String user, String password, String query, String csvFilePath) {
    Connection conn = null;
    Statement stmt = null;
    ResultSet rs = null;
    FileWriter writer = null;
    
    try {
        conn = DriverManager.getConnection(url, user, password);
        stmt = conn.createStatement();
        rs = stmt.executeQuery(query);
        writer = new FileWriter(csvFilePath);
        
        ResultSetMetaData metaData = rs.getMetaData();
        int columnCount = metaData.getColumnCount();
        
        // Writing the header
        for (int i = 1; i <= columnCount; i++) {
            writer.append(escapeCSV(metaData.getColumnName(i)));
            if (i < columnCount) writer.append(",");
        }
        writer.append("\n");

        // Writing data rows
        while (rs.next()) {
            for (int i = 1; i <= columnCount; i++) {
                writer.append(escapeCSV(rs.getString(i)));
                if (i < columnCount) writer.append(",");
            }
            writer.append("\n");
        }

        System.out.println("CSV file saved: " + csvFilePath);
    } catch (SQLException | IOException e) {
        e.printStackTrace();
    } finally {
        try {
            if (writer != null) writer.close();
            if (rs != null) rs.close();
            if (stmt != null) stmt.close();
            if (conn != null) conn.close();
        } catch (IOException | SQLException e) {
            e.printStackTrace();
        }
    }
}






                                 import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;

import java.io.IOException;
import java.io.InputStream;
import java.sql.Connection;
import java.sql.SQLException;
import java.util.Properties;

public class DBConnectionManager {
    private static HikariDataSource dataSource;

    static {
        try (InputStream input = DBConnectionManager.class.getClassLoader().getResourceAsStream("db.properties")) {
            Properties props = new Properties();
            if (input == null) {
                throw new RuntimeException("db.properties not found in classpath");
            }
            props.load(input);

            HikariConfig config = new HikariConfig();
            config.setJdbcUrl(props.getProperty("db.url"));
            config.setUsername(props.getProperty("db.username"));
            config.setPassword(props.getProperty("db.password"));

            // Pool settings
            config.setMaximumPoolSize(Integer.parseInt(props.getProperty("db.pool.size", "10")));
            config.setMinimumIdle(2);
            config.setIdleTimeout(30000);
            config.setConnectionTimeout(10000);

            dataSource = new HikariDataSource(config);
        } catch (IOException e) {
            throw new RuntimeException("Error loading DB config", e);
        }
    }

    public static Connection getConnection() throws SQLException {
        return dataSource.getConnection();
    }
}

