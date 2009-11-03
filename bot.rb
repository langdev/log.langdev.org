require 'dbm'
require 'timeout'

require 'rubygems'
require 'eventmachine'
require 'rfeedparser'
require 'logger-1.2.7'

FeedItem = Struct.new :feed_title, :title, :url

class FeedList < Array
	def delete(url)
		super
		save
	end

	def push(url)
		super
		save
	end

	def save
		f = File.open('feeds', 'w')
		f.write self.join("\n")
		f.close
	end

	def load
		clear
		f = File.open('feeds', 'r')
		for line in f.lines
			push line.rstrip
		end
		f.close
	end
end

class FeedChecker
	Period = 60 * 5

	def initialize
		@feeds = FeedList.new
	end

	def feeds
		@feeds.load
		@feeds
	end

	def updates
		feeds.collect { |url| updates_for url }.flatten
	end

	def updates_for(url)
		begin
			db = DBM.new('entries.dbm')
			f = FeedParser.parse(url)
			entries = f.entries.reject {
				|e| db.has_key?(e['id'] || e.link)
			}.each {
				|e| db[e['id'] || e.link] = 1
			}.map {
				|e| FeedItem.new(f.feed.title, e.title, e.link)
			}
			db.close
			return entries
		rescue Timeout::Error
			return []
		rescue
			return []
		end
	end
end

class IRC < EventMachine::Protocols::LineAndTextProtocol
	def initialize *args
		super
		@checker = args[0]
		@logger = args[1]
		@channel = '#langdev'
	end

	def post_init
		send_line "NICK 낚지"
		send_line "USER bot 0 * :fishing"
	end

	def receive_line(data)
		@logger.info '<<< ' + data

		case data
			when /^:(.+?) 001/
				on_welcome

			when /^:(.+?) PRIVMSG (.+?) :낚지.*? (.+)$/
				message = $3
				if message.match /^http:\/\//
					feed_url message
				else
					help
				end
			
			when /^PING/
				send_line data.sub(/^PING/, 'PONG')
		end
	end

	def send_line(line)
		@logger.info '>>> ' + line
		send_data(line + "\r\n")
	end

	def on_welcome
		send_line "JOIN #{@channel}"
	end

	def say(something)
		send_line "PRIVMSG #{@channel} :#{something}"
	end

	def notify_update(entry)
		say "#{nl2sp(entry.title)} -- #{entry.url} -- #{entry.feed_title}"
	end

	def help
		say "저는 #{@channel} 채널의 피드 알림 및 대화 기록 봇입니다. 피드를 추가하시려면 저에게 주소를 던져주세요."
		say "피드 목록, 소스 코드, 로그 등: http://ditto.just4fun.co.kr/bot/ | #{FeedChecker::Period}초마다 긁어옵니다."
	end

	def feed_url(url)
		if @checker.feeds.include?(url)
			@checker.feeds.delete url

			say "#{url}를 삭제했습니다."
		else
			@checker.feeds.push url
			say "#{url}를 추가했습니다."

			@checker.updates_for url
		end
	end

	def unbind
		EventMachine::stop_event_loop
	end
end

def nl2sp(str)
	str.gsub(/\n/, " ")
end

checker = FeedChecker.new
checker.updates # cache the updates

logger = Logger.new('logs/langdev.log', 'daily')
crawling = false

EM.error_handler do |e|
	logger.error e.message
end

EventMachine::run {
	connection = EventMachine::connect 'irc.ozinger.org', 6666, IRC, checker, logger

	EventMachine::PeriodicTimer.new(FeedChecker::Period) do
		EM.defer(proc do
			if crawling
				logger.info "crawling already"
				return
			end
			crawling = true
			logger.info "checking feed..."
			checker.updates.each do |entry|
				connection.notify_update(entry) if entry
			end
			crawling = false
		end)
	end
}

