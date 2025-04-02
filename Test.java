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

// Method to escape CSV values
private static String escapeCSV(String value) {
    if (value == null) {
        return "";
    }
    if (value.contains(",") || value.contains("\n") || value.contains("\"")) {
        value = value.replace("\"", "\"\""); // Escape double quotes
        return "\"" + value + "\""; // Enclose in double quotes
    }
    return value;
}

}

