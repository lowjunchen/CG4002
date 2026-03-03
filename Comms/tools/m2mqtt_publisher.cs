using System;
using System.Text;
using System.Threading;
using System.Security.Cryptography.X509Certificates;
using uPLibrary.Networking.M2Mqtt;
using uPLibrary.Networking.M2Mqtt.Messages;

class M2MqttPublisher
{
    static string GetArg(string[] args, string name, string fallback)
    {
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name)
                return args[i + 1];
        }
        return fallback;
    }

    static int GetArgInt(string[] args, string name, int fallback)
    {
        var s = GetArg(args, name, null);
        if (s == null) return fallback;
        if (int.TryParse(s, out var v)) return v;
        return fallback;
    }

    static int Main(string[] args)
    {
        string host = GetArg(args, "--host", "127.0.0.1");
        int port = GetArgInt(args, "--port", 8883);
        string topic1 = GetArg(args, "--topic1", "sensors/device/1");
        string topic2 = GetArg(args, "--topic2", "sensors/device/2");
        string caPath = GetArg(args, "--ca", "Comms/mosquitto/certs/ca.crt");
        string pfxPath = GetArg(args, "--pfx", "Comms/mosquitto/certs/clients/unity_pub.pfx");
        string pfxPass = GetArg(args, "--pfx-pass", "capstone");
        int intervalMs = GetArgInt(args, "--interval-ms", 250);
        int count = GetArgInt(args, "--count", 0); // 0 = infinite

        var caCert = new X509Certificate(caPath);
        var clientCert = new X509Certificate2(pfxPath, pfxPass);

        var clientId = "laptop_pub_" + Guid.NewGuid().ToString("N");
        var client = new MqttClient(host, port, true, caCert, clientCert, MqttSslProtocols.TLSv1_2);
        client.Connect(clientId);

        Console.WriteLine("Connected to {0}:{1} as {2}", host, port, clientId);
        Console.WriteLine("Publishing to {0} and {1} every {2} ms", topic1, topic2, intervalMs);

        int seq = 0;
        while (count == 0 || seq < count)
        {
            var ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            string payload1 = $"{{\"device\":1,\"type\":\"dummy\",\"seq\":{seq},\"ts\":{ts},\"value\":{(seq % 100)}}}";
            string payload2 = $"{{\"device\":2,\"type\":\"dummy\",\"seq\":{seq},\"ts\":{ts},\"value\":{((seq * 3) % 100)}}}";

            client.Publish(topic1, Encoding.UTF8.GetBytes(payload1), MqttMsgBase.QOS_LEVEL_0, false);
            client.Publish(topic2, Encoding.UTF8.GetBytes(payload2), MqttMsgBase.QOS_LEVEL_0, false);

            if (seq % 20 == 0)
                Console.WriteLine("Sent seq {0}", seq);

            seq++;
            Thread.Sleep(intervalMs);
        }

        client.Disconnect();
        return 0;
    }
}
