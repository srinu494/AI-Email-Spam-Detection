import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        try {
            Scanner sc = new Scanner(System.in);

            System.out.print("Enter Email Message: ");
            String message = sc.nextLine();

            URL url = new URL("http://127.0.0.1:5000/predict");

            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setDoOutput(true);

            String json = "{\"message\":\"" + message + "\"}";

            OutputStream os = conn.getOutputStream();
            os.write(json.getBytes());
            os.flush();
            os.close();

            Scanner response = new Scanner(conn.getInputStream());
            while (response.hasNext()) {
                System.out.println(response.nextLine());
            }

            response.close();
            sc.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
