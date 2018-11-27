from scrapy.commands.crawl import Command
from scrapy.exceptions import UsageError
from typing import List, Any


class StatusCommand(Command):
    def run(self, args: List[str], opts: Any) -> None:
        if len(args) < 1:
            raise UsageError()
        elif len(args) > 1:
            raise UsageError(
                "running 'scrapy crawl' with more than one spider is no longer supported")
        spname = args[0]

        crawler = self.crawler_process.create_crawler(spname)
        self.crawler_process.crawl(crawler)
        self.crawler_process.start()
        # Get exceptions quantity from crawler stat data

        if crawler.spider.has_error:
            # Return non-zero exit code if exceptions are contained
            self.exitcode = 1
